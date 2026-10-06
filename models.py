"""Typed domain models used throughout the application."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Quote:
    text: str
    author: str = "Unknown"
    category: str = "Life"
    source: str = "local"

    def normalized(self) -> str:
        return " ".join(self.text.split()).casefold()

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class GeneratedPost:
    date: str
    quote: Quote
    caption: str
    hashtags: list[str]
    image: str
    generated_at: str = field(default_factory=utc_now_iso)
    platforms: list[dict[str, Any]] = field(default_factory=list)
    status: str = "generated"
    video: str | None = None
    audio: str | None = None
    audio_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "quote": self.quote.to_dict(),
            "caption": self.caption,
            "hashtags": self.hashtags,
            "image": self.image,
            "video": self.video,
            "audio": self.audio,
            "audio_index": self.audio_index,
            "generated_at": self.generated_at,
            "platforms": self.platforms,
            "status": self.status,
        }
