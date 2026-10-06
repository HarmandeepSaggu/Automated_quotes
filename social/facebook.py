"""Facebook Page photo publisher."""
from __future__ import annotations

from social.base import BasePublisher, PostResult, SocialError, SocialPost


class FacebookPublisher(BasePublisher):
    platform = "facebook"

    def post(self, post: SocialPost) -> PostResult:
        token = self.require("FACEBOOK_TOKEN")
        config = self.settings.get("facebook", {})
        page_id = config.get("page_id") or self.environment.get("FACEBOOK_PAGE_ID", "")
        if not page_id:
            raise SocialError("Facebook page_id is not configured")
        version = config.get("api_version", "v20.0")
        with post.image_path.open("rb") as image:
            response = self.request(
                "POST", f"https://graph.facebook.com/{version}/{page_id}/photos",
                params={"access_token": token},
                data={"caption": post.text},
                files={"source": (post.image_path.name, image, "image/png")},
            ).json()
        post_id = response.get("post_id") or response.get("id")
        return PostResult(self.platform, True, "Facebook post published", str(post_id) if post_id else None)
