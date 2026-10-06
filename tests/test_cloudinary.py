from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cloudinary_uploader import CloudinaryUploader
from posting_engine import PostingEngine


class FakeUploadResponse:
    ok = True
    status_code = 200
    text = ""

    def json(self) -> dict[str, str]:
        return {"secure_url": "https://res.cloudinary.com/demo/video/upload/reel.mp4"}


class CloudinaryUploaderTests(unittest.TestCase):
    def test_signed_video_upload_returns_secure_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "daily-reel.mp4"
            video.write_bytes(b"video")
            environment = {
                "CLOUDINARY_CLOUD_NAME": "demo-cloud",
                "CLOUDINARY_API_KEY": "api-key",
                "CLOUDINARY_API_SECRET": "api-secret",
                "CLOUDINARY_FOLDER": "quotes/reels",
            }
            with patch("cloudinary_uploader.requests.post", return_value=FakeUploadResponse()) as upload:
                url = CloudinaryUploader(environment).upload_video(video)

        self.assertEqual(url, "https://res.cloudinary.com/demo/video/upload/reel.mp4")
        self.assertEqual(upload.call_args.args[0], "https://api.cloudinary.com/v1_1/demo-cloud/video/upload")
        self.assertEqual(upload.call_args.kwargs["data"]["api_key"], "api-key")
        self.assertEqual(len(upload.call_args.kwargs["data"]["signature"]), 40)

    def test_posting_engine_uses_cloudinary_before_public_video_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "daily-reel.mp4"
            video.write_bytes(b"video")
            engine = PostingEngine(
                Path(directory),
                {
                    "network": {"timeout_seconds": 30},
                    "platform_settings": {"instagram": {"media_type": "reels"}},
                },
                {
                    "CLOUDINARY_CLOUD_NAME": "demo-cloud",
                    "CLOUDINARY_UPLOAD_PRESET": "preset",
                    "PUBLIC_VIDEO_BASE_URL": "https://example.test/output",
                },
            )
            with patch.object(
                engine.cloudinary,
                "upload_video",
                return_value="https://res.cloudinary.com/demo/video/upload/reel.mp4",
            ) as upload:
                first = engine._video_url("instagram", video)
                second = engine._video_url("instagram", video)

        self.assertEqual(first, "https://res.cloudinary.com/demo/video/upload/reel.mp4")
        self.assertEqual(second, first)
        upload.assert_called_once_with(video)


if __name__ == "__main__":
    unittest.main()
