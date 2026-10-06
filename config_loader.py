"""Configuration loading and validation for Glimpse Of Thoughts."""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    """Raised when settings.yaml is missing or contains invalid values."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _defaults() -> dict[str, Any]:
    return {
        "brand": {"name": "Glimpse Of Thoughts", "lock_mode": True},
        "image": {
            "width": 1080,
            "height": 1350,
            "background": "#F5F3EF",
            "quote_color": "#2B2B2B",
            "signature_color": "#555555",
            "font_size": 36,
            "min_font_size": 34,
            "line_height": 1.4,
            "quote": {"x": 100, "y": 450, "width": 880, "max_lines": 4, "max_height": 220},
            "signature": {"x": 100, "y": 1000},
            "signature_font_size": 20,
            "fonts": [],
        },
        "quotes": {
            "source": "auto",
            "text_file": "quotes/quotes.txt",
            "csv_file": "quotes/quotes.csv",
            "categories": [],
        },
        "caption": {"max_lines": 2},
        "hashtags": {"count": 20},
        "openai": {"model": "gpt-4o-mini", "timeout_seconds": 30},
        "output": {
            "directory": "output",
            "history_file": "history/history.json",
            "date_format": "%Y-%m-%d",
        },
        "analytics": {"enabled": False, "file": "history/analytics.json"},
        "preview": {"enabled": True, "open_image": True},
        "platforms": [],
        "platform_settings": {
            "instagram": {
                "api_version": "v25.0",
                "api_host": "",
                "account_id": "",
                "media_type": "reels",
                "audio_directory": "Audio",
                "audio_rotation_file": "history/audio_rotation.json",
                "public_video_url": "",
                "share_to_feed": True,
                "container_timeout_seconds": 300,
                "container_poll_interval_seconds": 5,
                "video": {
                    "width": 1080,
                    "height": 1920,
                    "fps": 30,
                    "duration_seconds": 10,
                },
            },
        },
        "network": {"timeout_seconds": 30, "retries": 2},
    }


def _require_color(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.startswith("#") or len(value) not in (4, 7):
        raise ConfigurationError(f"{field} must be a #RGB or #RRGGBB color")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ConfigurationError(f"{field} must be a hexadecimal color") from exc


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    brand = settings.get("brand", {})
    image = settings.get("image", {})
    quote_layout = image.get("quote", {})
    signature = image.get("signature", {})
    if not str(brand.get("name", "")).strip():
        raise ConfigurationError("brand.name cannot be empty")
    for field in ("width", "height", "font_size", "min_font_size", "signature_font_size"):
        if type(image.get(field)) is not int or image[field] <= 0:
            raise ConfigurationError(f"image.{field} must be a positive integer")
    for field in ("x", "y", "width"):
        if type(quote_layout.get(field)) is not int or quote_layout[field] < 0:
            raise ConfigurationError(f"image.quote.{field} must be a non-negative integer")
    for field in ("x", "y"):
        if type(signature.get(field)) is not int or signature[field] < 0:
            raise ConfigurationError(f"image.signature.{field} must be a non-negative integer")
    if (type(image.get("line_height")) not in (int, float)
            or not math.isfinite(image["line_height"]) or image["line_height"] < 1.0):
        raise ConfigurationError("image.line_height must be finite and at least 1.0")
    if image["min_font_size"] > image["font_size"]:
        raise ConfigurationError("image.min_font_size cannot exceed image.font_size")
    for field in ("width", "max_lines", "max_height"):
        if type(quote_layout.get(field)) is not int or quote_layout[field] <= 0:
            raise ConfigurationError(f"image.quote.{field} must be a positive integer")
    if not 2 <= quote_layout["max_lines"] <= 4:
        raise ConfigurationError("image.quote.max_lines must be between 2 and 4")
    if quote_layout["x"] + quote_layout["width"] > image["width"]:
        raise ConfigurationError("image.quote extends beyond the canvas width")
    if quote_layout["y"] + quote_layout["max_height"] > image["height"]:
        raise ConfigurationError("image.quote extends beyond the canvas height")
    if quote_layout["y"] + quote_layout["max_height"] > signature["y"] - 40:
        raise ConfigurationError("Leave at least 40px between the quote area and signature")
    if signature["x"] >= image["width"] or signature["y"] >= image["height"]:
        raise ConfigurationError("image.signature must be inside the canvas")
    _require_color(image.get("background"), "image.background")
    _require_color(image.get("quote_color"), "image.quote_color")
    _require_color(image.get("signature_color"), "image.signature_color")

    count = settings.get("hashtags", {}).get("count")
    if not isinstance(count, int) or not 15 <= count <= 25:
        raise ConfigurationError("hashtags.count must be between 15 and 25")
    source = str(settings.get("quotes", {}).get("source", "auto")).lower()
    if source not in {"auto", "txt", "csv", "ai"}:
        raise ConfigurationError("quotes.source must be auto, txt, csv, or ai")
    platforms = settings.get("platforms", [])
    allowed = {"instagram", "facebook", "threads", "twitter", "pinterest"}
    if not isinstance(platforms, list) or any(str(p).lower() not in allowed for p in platforms):
        raise ConfigurationError(f"platforms must contain only: {', '.join(sorted(allowed))}")

    instagram = settings.get("platform_settings", {}).get("instagram", {})
    media_type = str(instagram.get("media_type", "image")).lower()
    if media_type not in {"image", "reels"}:
        raise ConfigurationError("platform_settings.instagram.media_type must be image or reels")
    if media_type == "reels":
        video = instagram.get("video", {})
        for field in ("width", "height", "fps"):
            if type(video.get(field)) is not int or video[field] <= 0:
                raise ConfigurationError(f"platform_settings.instagram.video.{field} must be a positive integer")
        if video["width"] % 2 or video["height"] % 2:
            raise ConfigurationError("Instagram Reel video width and height must be even numbers")
        if not 23 <= video["fps"] <= 60:
            raise ConfigurationError("Instagram Reel video.fps must be between 23 and 60")
        duration = video.get("duration_seconds")
        if type(duration) not in (int, float) or duration < 3 or duration > 900:
            raise ConfigurationError("Instagram Reel video.duration_seconds must be between 3 and 900")
        if not str(instagram.get("audio_directory", "")).strip():
            raise ConfigurationError("platform_settings.instagram.audio_directory cannot be empty")
        timeout = instagram.get("container_timeout_seconds")
        if type(timeout) is not int or timeout <= 0:
            raise ConfigurationError("Instagram container_timeout_seconds must be a positive integer")
        interval = instagram.get("container_poll_interval_seconds")
        if type(interval) not in (int, float) or interval < 0:
            raise ConfigurationError("Instagram container_poll_interval_seconds must be non-negative")
    return settings


def load_settings(config_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = (Path(root) if root else Path.cwd()) / path
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("settings.yaml must contain a mapping")
    settings = validate_settings(_deep_merge(_defaults(), raw))
    settings["_config_path"] = str(path.resolve())
    return settings


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(os.path.expandvars(str(value))).expanduser()
    return path if path.is_absolute() else root / path
