"""Upload generated Reel videos to Cloudinary and return HTTPS URLs."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class CloudinaryError(RuntimeError):
    """Raised when a video cannot be uploaded to Cloudinary."""


class CloudinaryUploader:
    """Small Cloudinary uploader using signed or unsigned upload credentials."""

    def __init__(self, environment: dict[str, str], timeout: int = 30):
        self.environment = environment
        self.timeout = timeout

    def _value(self, name: str) -> str:
        return self.environment.get(name, "").strip()

    def is_configured(self) -> bool:
        """Return whether the environment contains any Cloudinary setting."""
        return any(
            self._value(name)
            for name in (
                "CLOUDINARY_CLOUD_NAME",
                "CLOUDINARY_API_KEY",
                "CLOUDINARY_API_SECRET",
                "CLOUDINARY_UPLOAD_PRESET",
            )
        )

    def _upload_parameters(self) -> dict[str, str]:
        cloud_name = self._value("CLOUDINARY_CLOUD_NAME")
        api_key = self._value("CLOUDINARY_API_KEY")
        api_secret = self._value("CLOUDINARY_API_SECRET")
        upload_preset = self._value("CLOUDINARY_UPLOAD_PRESET")
        if not cloud_name:
            raise CloudinaryError("CLOUDINARY_CLOUD_NAME is required for Cloudinary uploads")

        timestamp = str(int(time.time()))
        parameters = {
            "timestamp": timestamp,
        }
        folder = self._value("CLOUDINARY_FOLDER")
        if folder:
            parameters["folder"] = folder

        # Prefer signed uploads when an API key and secret are available. An
        # upload preset is supported as a credential-free alternative.
        if api_key or api_secret:
            if not api_key or not api_secret:
                raise CloudinaryError(
                    "Set both CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET for signed uploads"
                )
            signature_source = "&".join(
                f"{key}={value}" for key, value in sorted(parameters.items()) if value
            )
            parameters.update({
                "api_key": api_key,
                "signature": hashlib.sha1(
                    f"{signature_source}{api_secret}".encode("utf-8")
                ).hexdigest(),
            })
        elif upload_preset:
            parameters["upload_preset"] = upload_preset
        else:
            raise CloudinaryError(
                "Cloudinary requires CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET, "
                "or CLOUDINARY_UPLOAD_PRESET"
            )
        return parameters

    def upload_video(self, video_path: Path) -> str:
        """Upload ``video_path`` as a Cloudinary video and return its HTTPS URL."""
        video_path = Path(video_path)
        if not video_path.is_file():
            raise CloudinaryError(f"Video file not found for Cloudinary upload: {video_path}")

        cloud_name = self._value("CLOUDINARY_CLOUD_NAME")
        parameters = self._upload_parameters()
        endpoint = (
            f"https://api.cloudinary.com/v1_1/{quote(cloud_name, safe='')}/video/upload"
        )
        try:
            with video_path.open("rb") as video_file:
                response = requests.post(
                    endpoint,
                    data=parameters,
                    files={"file": (video_path.name, video_file, "video/mp4")},
                    timeout=self.timeout,
                )
        except requests.RequestException as exc:
            raise CloudinaryError(f"Cloudinary network failure: {exc}") from exc
        except OSError as exc:
            raise CloudinaryError(f"Could not read video for Cloudinary upload: {exc}") from exc

        try:
            body: dict[str, Any] = response.json()
        except ValueError:
            body = {}

        if not response.ok:
            detail = body.get("error", {}).get("message") or response.text[:500].replace("\n", " ")
            raise CloudinaryError(f"Cloudinary upload failed (HTTP {response.status_code}): {detail}")

        url = str(body.get("secure_url") or body.get("url") or "").strip()
        if not url.startswith("https://"):
            raise CloudinaryError("Cloudinary did not return a public HTTPS video URL")
        return url
