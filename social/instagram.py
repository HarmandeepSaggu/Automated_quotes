"""Instagram Graph API publisher for image posts and Reels."""
from __future__ import annotations

import time
from typing import Any

from social.base import BasePublisher, PostResult, SocialError, SocialPost


class InstagramPublisher(BasePublisher):
    platform = "instagram"

    def _graph_host(self, token: str, config: dict[str, Any]) -> str:
        configured = str(
            config.get("api_host") or self.environment.get("INSTAGRAM_API_HOST", "")
        ).strip()
        if not configured:
            # Instagram Login tokens are used with graph.instagram.com;
            # Facebook Login user tokens are used with graph.facebook.com.
            configured = "graph.instagram.com" if token.startswith("IG") else "graph.facebook.com"
        configured = configured.removeprefix("https://").removeprefix("http://").rstrip("/")
        if configured not in {"graph.facebook.com", "graph.instagram.com"}:
            raise SocialError(
                "Instagram API host must be graph.facebook.com or graph.instagram.com"
            )
        return configured

    def _wait_for_container(self, version: str, container_id: str, token: str, config: dict[str, Any]) -> None:
        timeout = int(config.get("container_timeout_seconds", 300))
        interval = float(config.get("container_poll_interval_seconds", 5))
        deadline = time.monotonic() + timeout
        host = self._graph_host(token, config)
        status_url = f"https://{host}/{version}/{container_id}"
        last_status = "unknown"
        while True:
            status_response = self.request(
                "GET",
                status_url,
                params={"fields": "status_code", "access_token": token},
            ).json()
            last_status = str(status_response.get("status_code", "")).upper()
            if last_status in {"FINISHED", "PUBLISHED"}:
                return
            if last_status == "ERROR":
                detail = status_response.get("error_message") or status_response.get("status") or "unknown error"
                raise SocialError(f"Instagram Reel processing failed: {detail}")
            if time.monotonic() >= deadline:
                raise SocialError(
                    f"Instagram Reel container {container_id} did not finish within {timeout}s "
                    f"(last status: {last_status or 'unknown'})"
                )
            if interval:
                time.sleep(interval)

    def post(self, post: SocialPost) -> PostResult:
        token = self.require("INSTAGRAM_TOKEN")
        config = self.settings.get("instagram", {})
        account_id = config.get("account_id") or self.environment.get("INSTAGRAM_ACCOUNT_ID", "")
        if not account_id:
            raise SocialError("Instagram account_id is not configured")
        version = config.get("api_version", "v25.0")
        host = self._graph_host(token, config)
        base = f"https://{host}/{version}/{account_id}"
        media_type = str(config.get("media_type") or post.media_type or "image").lower()

        if media_type in {"reel", "reels"}:
            video_url = post.video_url or self.environment.get("PUBLIC_VIDEO_BASE_URL", "")
            if not video_url:
                raise SocialError(
                    "Instagram Reels require a public HTTPS video URL; configure public_video_url "
                    "or PUBLIC_VIDEO_BASE_URL"
                )
            data: dict[str, Any] = {
                "video_url": video_url,
                "media_type": "REELS",
                "caption": post.text,
                "access_token": token,
            }
            if "share_to_feed" in config:
                data["share_to_feed"] = "true" if bool(config["share_to_feed"]) else "false"
            container = self.request("POST", f"{base}/media", data=data).json()
            creation_id = container.get("id")
            if not creation_id:
                raise SocialError("Instagram did not return a Reel media container id")
            self._wait_for_container(version, str(creation_id), token, config)
            published = self.request("POST", f"{base}/media_publish", data={
                "creation_id": creation_id, "access_token": token,
            }).json()
            media_id = published.get("id")
            return PostResult(self.platform, True, "Instagram Reel published", str(media_id or creation_id))

        if media_type not in {"image", "photo"}:
            raise SocialError(f"Unsupported Instagram media_type: {media_type}")
        image_url = post.image_url or self.environment.get("PUBLIC_IMAGE_BASE_URL", "")
        if not image_url:
            raise SocialError("Instagram image posts require a public HTTPS image URL; configure public_image_url")
        container = self.request("POST", f"{base}/media", data={
            "image_url": image_url, "caption": post.text, "access_token": token,
        }).json()
        creation_id = container.get("id")
        if not creation_id:
            raise SocialError("Instagram did not return a media container id")
        published = self.request("POST", f"{base}/media_publish", data={
            "creation_id": creation_id, "access_token": token,
        }).json()
        media_id = published.get("id")
        return PostResult(self.platform, True, "Instagram image post published", str(media_id or creation_id))
