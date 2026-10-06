"""Optional local analytics for generated and published content."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from models import GeneratedPost


class AnalyticsError(RuntimeError):
    """Raised when analytics data cannot be persisted."""


class AnalyticsTracker:
    def __init__(self, root: Path, settings: dict[str, Any]):
        config = settings.get("analytics", {})
        self.enabled = bool(config.get("enabled", False))
        configured = config.get("file", "history/analytics.json")
        path = Path(str(configured)).expanduser()
        self.path = path if path.is_absolute() else root / path

    def record(self, post: GeneratedPost) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"version": 1, "events": []}
            if not isinstance(data, dict) or not isinstance(data.get("events", []), list):
                raise AnalyticsError("analytics file has an invalid structure")
            data["events"].append({
                "date": post.date,
                "status": post.status,
                "platforms": post.platforms,
                "quote_category": post.quote.category,
            })
            fd, temporary = tempfile.mkstemp(prefix=".analytics-", suffix=".json", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            except OSError:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise AnalyticsError(f"Cannot write analytics file {self.path}: {exc}") from exc
