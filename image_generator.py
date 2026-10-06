"""Brand-locked quote image rendering."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

from config_loader import resolve_path
from models import Quote
from text_layout import TextLayoutError, normalize_paragraph, wrap_paragraph

LOGGER = logging.getLogger("glimpse_of_thoughts")


class ImageGenerationError(RuntimeError):
    """Raised when the locked image cannot be rendered."""


@dataclass(frozen=True)
class QuoteLayout:
    lines: tuple[str, ...]
    font: ImageFont.FreeTypeFont
    font_size: int
    line_step: int
    baseline_offset: int
    left_offset: int
    height: int


class ImageGenerator:
    def __init__(self, root: Path, settings: dict[str, Any]):
        self.root = root
        self.settings = settings
        self.image_settings = settings["image"]

    def _font_candidates(self) -> Iterable[Path]:
        for value in self.image_settings.get("fonts", []):
            yield resolve_path(self.root, value)
        # Common locations make the same settings portable across Windows/Linux/macOS.
        for path in (
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/georgiai.ttf",
            Path("/Library/Fonts/Georgia Italic.ttf"),
            Path("/usr/share/fonts/truetype/msttcorefonts/Georgia_Italic.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"),
        ):
            yield path

    @lru_cache(maxsize=32)
    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        for path in self._font_candidates():
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError as exc:
                    LOGGER.warning("Unable to load font %s: %s", path, exc)
        LOGGER.warning("No preferred font found; using Pillow default font")
        return ImageFont.load_default(size=size)

    @staticmethod
    def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int = 4) -> list[str]:
        try:
            return wrap_paragraph(text, font, width, max_lines)
        except TextLayoutError as exc:
            raise ImageGenerationError(str(exc)) from exc

    def layout_quote(self, text: str) -> QuoteLayout:
        """Fit an intact paragraph into a bounded 1–4-line block, never tiny text."""
        text = normalize_paragraph(text)
        if not text:
            raise ImageGenerationError("Cannot render an empty quote")
        config = self.image_settings
        area = config["quote"]
        signature_y = config["signature"]["y"]
        max_height = min(area["max_height"], config["height"] - area["y"], signature_y - area["y"] - 40)
        for size in range(config["font_size"], config["min_font_size"] - 1, -1):
            font = self._load_font(size)
            try:
                lines = wrap_paragraph(text, font, area["width"], area["max_lines"])
            except TextLayoutError:
                continue
            # Baseline-to-baseline distance, not Pillow's *additional* spacing.
            step = round(size * config["line_height"])
            boxes = [font.getbbox(line, anchor="ls") for line in lines]
            top = min(box[1] for box in boxes)
            bottom = max(box[3] for box in boxes)
            if step < bottom - top:
                continue
            height = (len(lines) - 1) * step + bottom - top
            ink_width = max(box[2] for box in boxes) - min(0, *(box[0] for box in boxes))
            if height <= max_height and ink_width <= area["width"]:
                return QuoteLayout(tuple(lines), font, size, step, -top,
                                   -min(0, *(box[0] for box in boxes)), height)
        raise ImageGenerationError(
            f"Quote cannot fit within {area['max_lines']} lines and {max_height}px height "
            f"at a readable font size ({config['min_font_size']}px minimum). "
            "Shorten the quote or manually widen the quote area in settings.yaml."
        )

    def render(self, quote: Quote, destination: str | Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        width = int(self.image_settings["width"])
        height = int(self.image_settings["height"])
        background = self.image_settings["background"]
        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)

        signature_font = self._load_font(int(self.image_settings["signature_font_size"]))
        area = self.image_settings["quote"]
        layout = self.layout_quote(quote.text)
        for index, line in enumerate(layout.lines):
            draw.text(
                (area["x"] + layout.left_offset,
                 area["y"] + layout.baseline_offset + index * layout.line_step),
                line,
                font=layout.font,
                fill=self.image_settings["quote_color"],
                anchor="ls",
            )
        signature = self.image_settings["signature"]
        draw.text(
            (int(signature["x"]), int(signature["y"])),
            self.settings["brand"]["name"],
            font=signature_font,
            fill=self.image_settings["signature_color"],
        )
        try:
            image.save(destination, format="PNG", optimize=True)
        except OSError as exc:
            raise ImageGenerationError(f"Cannot save image {destination}: {exc}") from exc
        return destination
