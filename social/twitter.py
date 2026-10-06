"""X/Twitter publisher using Tweepy OAuth 1.0a media upload."""
from __future__ import annotations

from social.base import BasePublisher, PostResult, SocialError, SocialPost


class TwitterPublisher(BasePublisher):
    platform = "twitter"

    def post(self, post: SocialPost) -> PostResult:
        api_key = self.environment.get("TWITTER_API_KEY", "").strip()
        api_secret = self.environment.get("TWITTER_API_SECRET", "").strip()
        access_token = self.environment.get("TWITTER_ACCESS_TOKEN", "").strip() or self.environment.get("TWITTER_TOKEN", "").strip()
        access_secret = self.environment.get("TWITTER_ACCESS_TOKEN_SECRET", "").strip()
        if not all((api_key, api_secret, access_token, access_secret)):
            raise SocialError("Twitter requires TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, and TWITTER_ACCESS_TOKEN_SECRET")
        try:
            import tweepy
        except ImportError as exc:
            raise SocialError("Tweepy is not installed") from exc
        try:
            auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
            api = tweepy.API(auth, wait_on_rate_limit=True)
            media = api.media_upload(filename=str(post.image_path))
            client = tweepy.Client(consumer_key=api_key, consumer_secret=api_secret, access_token=access_token, access_token_secret=access_secret)
            response = client.create_tweet(text=post.text, media_ids=[media.media_id_string])
            tweet_id = (response.data or {}).get("id") if response else None
        except Exception as exc:  # Tweepy exposes several platform-specific exception classes.
            raise SocialError(f"Twitter publishing failed: {exc}") from exc
        return PostResult(self.platform, True, "Twitter post published", str(tweet_id) if tweet_id else None)
