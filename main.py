"""Daily entry point for Glimpse Of Thoughts.

Run from the project root with ``python main.py``.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from analytics import AnalyticsError, AnalyticsTracker
from audio_rotation import AudioRotation, AudioRotationError, AudioSelection
from caption_generator import CaptionGenerator
from config_loader import ConfigurationError, load_settings, resolve_path
from hashtag_engine import HashtagEngine
from history_manager import HistoryError, HistoryManager
from image_generator import ImageGenerationError, ImageGenerator
from logging_setup import configure_logging
from models import GeneratedPost
from posting_engine import PostingEngine
from preview import show_preview
from quote_engine import QuoteEngine, QuoteError
from reel_generator import ReelGenerationError, ReelGenerator

LOGGER = logging.getLogger("glimpse_of_thoughts")
ROOT = Path(__file__).resolve().parent


def atomic_json_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".post-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate, preview, and optionally publish a daily quote post.")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to settings.yaml")
    parser.add_argument("--source", choices=("auto", "txt", "csv", "ai"), help="Override quote source")
    parser.add_argument("--date", dest="post_date", help="Post date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--yes", action="store_true", help="Approve posting without asking (for controlled automation)")
    parser.add_argument("--dry-run", action="store_true", help="Generate and preview without publishing or prompting")
    parser.add_argument("--no-preview", action="store_true", help="Do not open the graphical preview")
    parser.add_argument("--force", action="store_true", help="Allow replacement of existing output for this run")
    parser.add_argument(
        "--run-id",
        help="Optional stable identifier for a scheduled slot, such as morning or night",
    )
    return parser.parse_args()


def record_analytics(settings: dict[str, Any], post: GeneratedPost, logger: logging.Logger) -> None:
    try:
        AnalyticsTracker(ROOT, settings).record(post)
    except AnalyticsError as exc:
        # Analytics must never turn a successful generation/post into a failed job.
        logger.warning("Analytics failure | %s", exc)


def instagram_reels_enabled(settings: dict[str, Any]) -> bool:
    platforms = {str(platform).lower().strip() for platform in settings.get("platforms", [])}
    instagram = settings.get("platform_settings", {}).get("instagram", {})
    return "instagram" in platforms and str(instagram.get("media_type", "image")).lower() in {"reel", "reels"}


def instagram_posted(results: list[dict[str, Any]]) -> bool:
    return any(
        str(result.get("platform", "")).lower() == "instagram" and bool(result.get("success"))
        for result in results
    )


def relative_to_root(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def ask_for_confirmation() -> bool:
    try:
        answer = input("\nPost this content? (Y/N) ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo confirmation received; content was not posted.")
        return False
    return answer in {"y", "yes"}


def output_stem(date_string: str, run_id: str | None) -> str:
    """Return a safe output name, allowing multiple posts on one date."""
    if not run_id:
        return date_string
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip(".-_")
    if not cleaned:
        raise ValueError("--run-id must contain at least one letter or number")
    return f"{date_string}-{cleaned[:64]}"


def main() -> int:
    args = parse_args()
    # The project-local .env is the source of truth for this desktop workflow.
    # Override stale values inherited from a previous PowerShell session.
    load_dotenv(ROOT / ".env", override=True)
    # Configure logging as early as possible, even if settings are invalid.
    logger = configure_logging(ROOT / "logs" / "app.log")
    try:
        settings = load_settings(args.config, ROOT)
        if args.source:
            settings["quotes"]["source"] = args.source
        post_date = date.fromisoformat(args.post_date) if args.post_date else date.today()
        date_string = post_date.strftime(settings["output"].get("date_format", "%Y-%m-%d"))
        file_stem = output_stem(date_string, args.run_id)
        output_dir = resolve_path(ROOT, settings["output"]["directory"])
        image_path = output_dir / f"{file_stem}.png"
        metadata_path = output_dir / f"{file_stem}.json"
        caption_path = output_dir / f"{file_stem}-caption.txt"
        if image_path.exists() and not args.force:
            raise RuntimeError(f"Output already exists for {file_stem}; use --force to replace it")

        history = HistoryManager(resolve_path(ROOT, settings["output"]["history_file"]))
        quote = QuoteEngine(ROOT, settings, history).next_quote()
        caption = CaptionGenerator().generate(quote)
        hashtags = HashtagEngine(int(settings["hashtags"]["count"])).generate(quote)
        ImageGenerator(ROOT, settings).render(quote, image_path)
        image_relative = relative_to_root(image_path)
        audio_rotation: AudioRotation | None = None
        audio_selection: AudioSelection | None = None
        video_path: Path | None = None
        if instagram_reels_enabled(settings):
            audio_rotation = AudioRotation(ROOT, settings)
            audio_selection = audio_rotation.select()
            video_path = output_dir / f"{file_stem}-reel.mp4"
            ReelGenerator(ROOT, settings).render(image_path, video_path, audio_selection.path)
            logger.info(
                "Reel generation success | video=%s | audio=%s | audio_index=%s",
                relative_to_root(video_path),
                relative_to_root(audio_selection.path),
                audio_selection.index,
            )
        post = GeneratedPost(
            date_string,
            quote,
            caption,
            hashtags,
            image_relative,
            video=relative_to_root(video_path) if video_path else None,
            audio=relative_to_root(audio_selection.path) if audio_selection else None,
            audio_index=audio_selection.index if audio_selection else None,
        )
        atomic_json_write(metadata_path, post.to_dict())
        caption_path.parent.mkdir(parents=True, exist_ok=True)
        caption_path.write_text(caption + "\n\n" + " ".join(hashtags) + "\n", encoding="utf-8")
        logger.info("Generation success | date=%s | image=%s", date_string, image_relative)

        preview_settings = settings.get("preview", {})
        if preview_settings.get("enabled", True) and not args.no_preview:
            show_preview(post, image_path, open_image=bool(preview_settings.get("open_image", True)))

        approved = False if args.dry_run else (True if args.yes else ask_for_confirmation())
        if not approved:
            post.status = "cancelled" if not args.dry_run else "dry_run"
            atomic_json_write(metadata_path, post.to_dict())
            history.record(post)
            record_analytics(settings, post, logger)
            logger.info("Posting skipped | status=%s", post.status)
            print("\nContent saved but not posted.")
            return 0

        if not settings.get("platforms"):
            post.status = "approved"
            atomic_json_write(metadata_path, post.to_dict())
            history.record(post)
            record_analytics(settings, post, logger)
            logger.info("Posting skipped | no platforms configured")
            print("\nContent approved and saved. No social platforms are configured.")
            return 0

        results = PostingEngine(ROOT, settings).post(post, image_path)
        post.platforms = results
        post.status = "posted" if any(item.get("success") for item in results) else "posting_failed"
        atomic_json_write(metadata_path, post.to_dict())
        history.record(post)
        if audio_rotation and audio_selection and instagram_posted(results):
            try:
                audio_rotation.advance(audio_selection)
            except AudioRotationError as exc:
                # The Reel is already published; leave a visible warning so the
                # next run can be corrected instead of hiding a possible repeat.
                logger.error("Audio rotation could not advance | error=%s", exc)
        record_analytics(settings, post, logger)
        if post.status == "posted":
            logger.info("Posting complete | date=%s", date_string)
            print("\nPosting complete.")
            return 0
        logger.error("Posting failed on all configured platforms")
        print("\nNo platform completed successfully. Review logs/app.log.")
        return 1 if settings.get("platforms") else 0
    except (
        ConfigurationError,
        QuoteError,
        HistoryError,
        ImageGenerationError,
        AudioRotationError,
        ReelGenerationError,
        ValueError,
        OSError,
        RuntimeError,
    ) as exc:
        logger.error("Generation failure | %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # Last-resort safety net for unattended runs.
        logger.exception("Unexpected application failure")
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
