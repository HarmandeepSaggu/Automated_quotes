"""Pinterest API pin publisher."""
from __future__ import annotations

from social.base import BasePublisher, PostResult, SocialError, SocialPost


class PinterestPublisher(BasePublisher):
    platform = "pinterest"

    def post(self, post: SocialPost) -> PostResult:
        token = self.require("PINTEREST_TOKEN")
        config = self.settings.get("pinterest", {})
        board_id = config.get("board_id") or self.environment.get("PINTEREST_BOARD_ID", "")
        image_url = post.image_url or self.environment.get("PUBLIC_IMAGE_BASE_URL", "")
        if not board_id:
            raise SocialError("Pinterest board_id is not configured")
        if not image_url:
            raise SocialError("Pinterest requires a public HTTPS image URL; configure public_image_url")
        response = self.request(
            "POST", "https://api.pinterest.com/v5/pins",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "board_id": board_id,
                "title": self.settings.get("brand", {}).get("name", "Glimpse Of Thoughts"),
                "description": post.text,
                "media_source": {"source_type": "image_url", "url": image_url},
            },
        ).json()
        pin_id = response.get("id")
        return PostResult(self.platform, True, "Pinterest pin published", str(pin_id) if pin_id else None)
