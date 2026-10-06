from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audio_rotation import AudioRotation, AudioRotationError
from social.base import SocialPost
from social.instagram import InstagramPublisher


class FakeResponse:
    def __init__(self, body: dict[str, str]):
        self.body = body

    def json(self) -> dict[str, str]:
        return self.body


class AudioRotationTests(unittest.TestCase):
    def test_audio_files_rotate_alphabetically_and_persist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "Audio"
            audio.mkdir()
            (audio / "B.mp3").write_bytes(b"b")
            (audio / "A.mp3").write_bytes(b"a")
            settings = {
                "platform_settings": {
                    "instagram": {
                        "audio_directory": "Audio",
                        "audio_rotation_file": "history/audio_rotation.json",
                    }
                }
            }
            rotation = AudioRotation(root, settings)
            first = rotation.select()
            self.assertEqual(first.index, 0)
            self.assertEqual(first.path.name, "A.mp3")
            rotation.advance(first)

            second = AudioRotation(root, settings).select()
            self.assertEqual(second.index, 1)
            self.assertEqual(second.path.name, "B.mp3")
            rotation.advance(second)
            self.assertEqual(AudioRotation(root, settings).select().path.name, "A.mp3")

    def test_missing_audio_files_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = {"platform_settings": {"instagram": {"audio_directory": "Audio"}}}
            with self.assertRaises(AudioRotationError):
                AudioRotation(Path(directory), settings).select()


class InstagramReelPublisherTests(unittest.TestCase):
    def test_reel_waits_for_processing_then_publishes(self) -> None:
        settings = {
            "instagram": {
                "account_id": "account-1",
                "api_version": "v25.0",
                "media_type": "reels",
                "share_to_feed": True,
                "container_timeout_seconds": 1,
                "container_poll_interval_seconds": 0,
            }
        }
        publisher = InstagramPublisher(settings, {"INSTAGRAM_TOKEN": "token"})
        post = SocialPost(
            caption="A caption",
            hashtags=["#quote"],
            image_path=Path("quote.png"),
            video_url="https://cdn.example.test/quote-reel.mp4",
            media_type="reels",
        )
        responses = [
            FakeResponse({"id": "container-1"}),
            FakeResponse({"status_code": "FINISHED"}),
            FakeResponse({"id": "media-1"}),
        ]
        with patch.object(publisher, "request", side_effect=responses) as request:
            result = publisher.post(post)

        self.assertTrue(result.success)
        self.assertEqual(result.external_id, "media-1")
        self.assertEqual(request.call_count, 3)
        create_call = request.call_args_list[0]
        self.assertEqual(create_call.args[0], "POST")
        self.assertEqual(create_call.kwargs["data"]["media_type"], "REELS")
        self.assertEqual(create_call.kwargs["data"]["video_url"], post.video_url)
        self.assertEqual(request.call_args_list[1].args[0], "GET")

    def test_instagram_login_token_uses_instagram_graph_host(self) -> None:
        settings = {
            "instagram": {
                "account_id": "account-1",
                "api_version": "v25.0",
                "media_type": "reels",
                "container_timeout_seconds": 1,
                "container_poll_interval_seconds": 0,
            }
        }
        publisher = InstagramPublisher(settings, {"INSTAGRAM_TOKEN": "IG-test-token"})
        post = SocialPost(
            caption="A caption",
            hashtags=["#quote"],
            image_path=Path("quote.png"),
            video_url="https://cdn.example.test/quote-reel.mp4",
            media_type="reels",
        )
        responses = [
            FakeResponse({"id": "container-1"}),
            FakeResponse({"status_code": "FINISHED"}),
            FakeResponse({"id": "media-1"}),
        ]
        with patch.object(publisher, "request", side_effect=responses) as request:
            publisher.post(post)

        self.assertTrue(request.call_args_list[0].args[1].startswith("https://graph.instagram.com/"))


if __name__ == "__main__":
    unittest.main()
