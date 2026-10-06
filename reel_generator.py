"""Create an Instagram-compatible vertical Reel from a generated quote image."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class ReelGenerationError(RuntimeError):
    """Raised when a Reel video cannot be rendered."""


class ReelGenerator:
    def __init__(self, root: Path, settings: dict[str, Any]):
        self.root = root
        self.settings = settings
        instagram = settings.get("platform_settings", {}).get("instagram", {})
        video = instagram.get("video", {})
        self.width = int(video.get("width", 1080))
        self.height = int(video.get("height", 1920))
        self.fps = int(video.get("fps", 30))
        self.duration = float(video.get("duration_seconds", 10))

    def _frame(self, image_path: Path):
        try:
            from PIL import Image
        except ImportError as exc:
            raise ReelGenerationError("Pillow is required to generate Instagram Reels") from exc

        if not image_path.exists():
            raise ReelGenerationError(f"Generated image not found: {image_path}")
        try:
            source = Image.open(image_path).convert("RGB")
        except OSError as exc:
            raise ReelGenerationError(f"Cannot read generated image {image_path}: {exc}") from exc

        background = self.settings.get("image", {}).get("background", "#F5F3EF")
        canvas = Image.new("RGB", (self.width, self.height), background)
        scale = min(self.width / source.width, self.height / source.height)
        resized = source.resize(
            (round(source.width * scale), round(source.height * scale)),
            Image.Resampling.LANCZOS,
        )
        left = (self.width - resized.width) // 2
        top = (self.height - resized.height) // 2
        canvas.paste(resized, (left, top))
        return canvas

    def _validate(self, audio_path: Path | None) -> None:
        if self.width <= 0 or self.height <= 0 or self.width % 2 or self.height % 2:
            raise ReelGenerationError("Reel video width and height must be positive even numbers")
        if not 23 <= self.fps <= 60:
            raise ReelGenerationError("Reel video fps must be between 23 and 60")
        if self.duration < 3 or self.duration > 900:
            raise ReelGenerationError("Reel video duration must be between 3 and 900 seconds")
        if audio_path is not None and not audio_path.exists():
            raise ReelGenerationError(f"Selected audio file not found: {audio_path}")

    def _command(self, ffmpeg: str, audio_path: Path | None, target: Path) -> list[str]:
        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            str(self.fps),
            "-i",
            "-",
        ]
        if audio_path is not None:
            # Loop short clips so a configured Reel duration is always filled.
            command.extend(["-stream_loop", "-1", "-i", str(audio_path)])
        command.extend(["-map", "0:v:0"])
        if audio_path is not None:
            command.extend([
                "-map",
                "1:a:0",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
            ])
        command.extend([
            "-c:v",
            "libx264",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(self.fps),
            "-t",
            str(self.duration),
            "-movflags",
            "+faststart",
            str(target),
        ])
        return command

    def render(self, image_path: str | Path, target: str | Path, audio_path: str | Path | None) -> Path:
        image_path = Path(image_path)
        target = Path(target)
        audio = Path(audio_path) if audio_path is not None else None
        self._validate(audio)
        frame = self._frame(image_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError as exc:
            raise ReelGenerationError(
                "imageio-ffmpeg is required to generate Reels; install requirements.txt"
            ) from exc
        except OSError as exc:
            raise ReelGenerationError(f"Cannot locate an FFmpeg executable: {exc}") from exc

        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                self._command(ffmpeg, audio, target),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if process.stdin is None:
                raise ReelGenerationError("FFmpeg input pipe was not created")
            raw_frame = frame.tobytes()
            for _ in range(round(self.duration * self.fps)):
                process.stdin.write(raw_frame)
            process.stdin.close()
            error_output = process.stderr.read() if process.stderr is not None else b""
            return_code = process.wait()
        except (BrokenPipeError, OSError) as exc:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            raise ReelGenerationError(f"FFmpeg could not render the Reel: {exc}") from exc
        finally:
            if process is not None and process.stdin is not None and not process.stdin.closed:
                process.stdin.close()

        if return_code != 0:
            target.unlink(missing_ok=True)
            detail = error_output.decode("utf-8", errors="replace").strip()
            raise ReelGenerationError(f"FFmpeg failed to render the Reel{': ' + detail if detail else ''}")
        return target
