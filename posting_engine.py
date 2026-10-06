"""Dispatch approved content to independently configured platforms."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from cloudinary_uploader import CloudinaryError, CloudinaryUploader
from models import GeneratedPost
from social.base import BasePublisher, PostResult, SocialError, SocialPost
from social.facebook import FacebookPublisher
from social.instagram import InstagramPublisher
from social.pinterest import PinterestPublisher
from social.threads import ThreadsPublisher
from social.twitter import TwitterPublisher

LOGGER = logging.getLogger("glimpse_of_thoughts")


class PostingEngine:
    _publishers: dict[str, type[BasePublisher]] = {
        "instagram": InstagramPublisher,
        "facebook": FacebookPublisher,
        "threads": ThreadsPublisher,
        "twitter": TwitterPublisher,
        "pinterest": PinterestPublisher,
    }

    def __init__(self, root: Path, settings: dict[str, Any], environment: dict[str, str] | None = None):
        self.root = root
        self.settings = settings
        self.environment = environment or dict(os.environ)
        self.timeout = int(settings.get("network", {}).get("timeout_seconds", 30))
        self.cloudinary = CloudinaryUploader(self.environment, self.timeout)
        self._uploaded_video_urls: dict[Path, str] = {}

    def _image_url(self, platform: str, image_path: Path) -> str | None:
        platform_settings = self.settings.get("platform_settings", {}).get(platform, {})
        configured = str(platform_settings.get("public_image_url", "")).strip()
        if not configured:
            configured = self.environment.get("PUBLIC_IMAGE_BASE_URL", "").strip()
        if not configured:
            return None
        if configured.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            return configured
        return urljoin(configured.rstrip("/") + "/", image_path.name)

    def _video_url(self, platform: str, video_path: Path | None) -> str | None:
        if video_path is None:
            return None
        platform_settings = self.settings.get("platform_settings", {}).get(platform, {})
        media_type = str(platform_settings.get("media_type", "image")).lower()
        if platform == "instagram" and media_type not in {"reel", "reels"}:
            return None
        configured = str(platform_settings.get("public_video_url", "")).strip()
        if configured:
            return self._url_from_base(configured, video_path)

        # Cloudinary provides the public HTTPS URL required by Instagram. It
        # takes precedence over the legacy static public-directory setting so
        # generated videos do not need to be copied to a separate web server.
        if self.cloudinary.is_configured():
            cache_key = video_path.resolve()
            if cache_key not in self._uploaded_video_urls:
                self._uploaded_video_urls[cache_key] = self.cloudinary.upload_video(video_path)
            return self._uploaded_video_urls[cache_key]

        configured = self.environment.get("PUBLIC_VIDEO_BASE_URL", "").strip()
        if not configured:
            return None
        return self._url_from_base(configured, video_path)

    @staticmethod
    def _url_from_base(configured: str, media_path: Path) -> str:
        if configured.lower().endswith((".mp4", ".mov", ".m4v")):
            return configured
        return urljoin(configured.rstrip("/") + "/", media_path.name)

    def post(self, post: GeneratedPost, image_path: str | Path) -> list[dict[str, Any]]:
        image_path = Path(image_path)
        video_path = None
        if post.video:
            candidate = Path(post.video)
            video_path = candidate if candidate.is_absolute() else self.root / candidate
        results: list[dict[str, Any]] = []
        social_post_base = {
            "caption": post.caption,
            "hashtags": post.hashtags,
            "image_path": image_path,
            "video_path": video_path,
        }
        for configured in self.settings.get("platforms", []):
            platform = str(configured).lower().strip()
            publisher_type = self._publishers.get(platform)
            if not publisher_type:
                results.append(PostResult(platform, False, "Unsupported platform").__dict__)
                continue
            try:
                platform_config = self.settings.get("platform_settings", {}).get(platform, {})
                # Platform adapters read their own named configuration section.
                publisher = publisher_type(
                    {platform: platform_config, "brand": self.settings.get("brand", {})},
                    self.environment,
                    self.timeout,
                )
                media_type = str(platform_config.get("media_type", "image")).lower()
                social_post = SocialPost(
                    **social_post_base,
                    image_url=self._image_url(platform, image_path),
                    video_url=self._video_url(platform, video_path),
                    media_type=media_type,
                )
                result = publisher.post(social_post)
                LOGGER.info("Posting success | platform=%s | external_id=%s", platform, result.external_id or "n/a")
            except (CloudinaryError, SocialError, OSError, ValueError) as exc:
                result = PostResult(platform, False, str(exc))
                LOGGER.error("Posting failure | platform=%s | error=%s", platform, exc)
            results.append(result.__dict__)
        return results
