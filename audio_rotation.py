"""Deterministic, persistent rotation for local Reel audio files."""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

from config_loader import resolve_path


class AudioRotationError(RuntimeError):
    """Raised when Reel audio cannot be discovered or its state cannot be saved."""


AUDIO_SUFFIXES = frozenset({".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"})


@dataclass(frozen=True)
class AudioSelection:
    index: int
    path: Path


class AudioRotation:
    """Choose audio alphabetically and advance only after Instagram succeeds.

    Selection is intentionally separate from advancement so cancelled, dry-run, or
    failed posts reuse the same audio on the next attempt.
    """

    def __init__(self, root: Path, settings: dict[str, Any]):
        instagram = settings.get("platform_settings", {}).get("instagram", {})
        self.audio_directory = resolve_path(root, instagram.get("audio_directory", "Audio"))
        self.state_path = resolve_path(
            root,
            instagram.get("audio_rotation_file", "history/audio_rotation.json"),
        )
        self._lock = RLock()

    def files(self) -> list[Path]:
        if not self.audio_directory.exists():
            raise AudioRotationError(f"Instagram audio directory not found: {self.audio_directory}")
        if not self.audio_directory.is_dir():
            raise AudioRotationError(f"Instagram audio path is not a directory: {self.audio_directory}")
        files = sorted(
            (path for path in self.audio_directory.iterdir()
             if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES),
            key=lambda path: path.name.casefold(),
        )
        if not files:
            supported = ", ".join(sorted(AUDIO_SUFFIXES))
            raise AudioRotationError(
                f"No supported audio files found in {self.audio_directory}; expected: {supported}"
            )
        return files

    @contextmanager
    def _process_lock(self) -> Iterator[None]:
        lock_path = self.state_path.with_suffix(self.state_path.suffix + ".lock")
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

    def _read_index(self, count: int) -> int:
        if not self.state_path.exists():
            return 0
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            value = data.get("next_index", 0) if isinstance(data, dict) else 0
            if type(value) is not int or value < 0:
                raise ValueError("next_index must be a non-negative integer")
            return value % count
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise AudioRotationError(f"Cannot read audio rotation state {self.state_path}: {exc}") from exc

    def _write_index(self, index: int) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".audio-rotation-", suffix=".json", dir=self.state_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "next_index": index}, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.state_path)
        except OSError as exc:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise AudioRotationError(f"Cannot write audio rotation state {self.state_path}: {exc}") from exc

    def select(self) -> AudioSelection:
        files = self.files()
        with self._lock, self._process_lock():
            index = self._read_index(len(files))
        return AudioSelection(index, files[index])

    def advance(self, selection: AudioSelection) -> None:
        """Advance after a successful Instagram Reel, without skipping concurrent state."""
        files = self.files()
        with self._lock, self._process_lock():
            current = self._read_index(len(files))
            if current != selection.index % len(files):
                # Another successful run already advanced the state.
                return
            self._write_index((selection.index + 1) % len(files))
