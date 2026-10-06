"""Common social publisher contracts and safe HTTP helpers."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger("glimpse_of_thoughts")


class SocialError(RuntimeError):
    """A platform-specific publishing or credential error."""


@dataclass
class SocialPost:
    caption: str
    hashtags: list[str]
    image_path: Path
    image_url: str | None = None
    video_path: Path | None = None
    video_url: str | None = None
    media_type: str = "image"

    @property
    def text(self) -> str:
        tags = " ".join(self.hashtags)
        return f"{self.caption}\n\n{tags}".strip()


@dataclass
class PostResult:
    platform: str
    success: bool
    message: str
    external_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class BasePublisher:
    platform = "unknown"

    def __init__(self, settings: dict[str, Any], environment: dict[str, str], timeout: int = 30):
        self.settings = settings
        self.environment = environment
        self.timeout = timeout

    def require(self, *names: str) -> str:
        for name in names:
            value = self.environment.get(name, "").strip()
            if value:
                return value
        raise SocialError(f"Missing credentials: set one of {', '.join(names)}")

    def session(self) -> requests.Session:
        retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session().request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise SocialError(f"Network failure: {exc}") from exc
        if not response.ok:
            detail = response.text[:500].replace("\n", " ")
            raise SocialError(f"HTTP {response.status_code}: {detail}")
        return response

    def post(self, post: SocialPost) -> PostResult:
        raise NotImplementedError
