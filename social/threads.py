"""Threads API publisher."""
from __future__ import annotations

from social.base import BasePublisher, PostResult, SocialError, SocialPost


class ThreadsPublisher(BasePublisher):
    platform = "threads"

    def post(self, post: SocialPost) -> PostResult:
        token = self.require("THREADS_TOKEN")
        config = self.settings.get("threads", {})
        user_id = config.get("user_id") or self.environment.get("THREADS_USER_ID", "")
        image_url = post.image_url or self.environment.get("PUBLIC_IMAGE_BASE_URL", "")
        if not user_id:
            raise SocialError("Threads user_id is not configured")
        if not image_url:
            raise SocialError("Threads requires a public HTTPS image URL; configure public_image_url")
        version = config.get("api_version", "v1.0")
        base = f"https://graph.threads.net/{version}/{user_id}"
        container = self.request("POST", f"{base}/threads", data={
            "media_type": "IMAGE", "image_url": image_url, "text": post.text, "access_token": token,
        }).json()
        creation_id = container.get("id")
        if not creation_id:
            raise SocialError("Threads did not return a media container id")
        published = self.request("POST", f"{base}/threads_publish", data={
            "creation_id": creation_id, "access_token": token,
        }).json()
        return PostResult(self.platform, True, "Threads post published", str(published.get("id") or creation_id))
