"""Atomic, duplicate-safe history persistence."""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

from models import GeneratedPost, Quote


class HistoryError(RuntimeError):
    """Raised when history cannot be read or written safely."""


class HistoryManager:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"version": 1, "posts": []})

    @contextmanager
    def _process_lock(self) -> Iterator[None]:
        """Lock a sidecar file so concurrent scheduled runs cannot reuse a quote."""
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock:
            if os.name == "nt":
                import msvcrt
                lock.seek(0)
                if lock.read(1) == b"":
                    lock.seek(0)
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HistoryError(f"Cannot read history file {self.path}: {exc}") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("posts", []), list):
            raise HistoryError(f"History file {self.path} has an invalid structure")
        return raw

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".history-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise HistoryError(f"Cannot write history file {self.path}: {exc}") from exc

    def used_quotes(self) -> set[str]:
        with self._lock, self._process_lock():
            data = self._read()
            values: set[str] = set()
            for post in data["posts"]:
                quote = post.get("quote", {})
                text = quote.get("text", "") if isinstance(quote, dict) else str(quote)
                if text:
                    values.add(" ".join(text.split()).casefold())
            return values

    def is_used(self, quote: Quote) -> bool:
        return quote.normalized() in self.used_quotes()

    def reserve_quote(self, quote: Quote) -> bool:
        """Atomically reserve a quote before expensive rendering or API work."""
        with self._lock, self._process_lock():
            data = self._read()
            normalized = quote.normalized()
            for existing in data["posts"]:
                existing_quote = existing.get("quote", {})
                text = existing_quote.get("text", "") if isinstance(existing_quote, dict) else str(existing_quote)
                if " ".join(text.split()).casefold() == normalized:
                    return False
            data["posts"].append({"quote": quote.to_dict(), "status": "reserved"})
            self._write(data)
            return True

    def record(self, post: GeneratedPost) -> None:
        with self._lock, self._process_lock():
            data = self._read()
            posts = data["posts"]
            # A date/image combination is idempotent, while a quote remains unique.
            for existing in posts:
                existing_quote = existing.get("quote", {})
                existing_text = existing_quote.get("text", "") if isinstance(existing_quote, dict) else str(existing_quote)
                if existing.get("image") == post.image or (
                    existing.get("status") == "reserved" and " ".join(existing_text.split()).casefold() == post.quote.normalized()
                ):
                    existing.clear()
                    existing.update(post.to_dict())
                    self._write(data)
                    return
            posts.append(post.to_dict())
            self._write(data)
