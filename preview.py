"""Human-friendly terminal and image preview."""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageShow

from models import GeneratedPost

LOGGER = logging.getLogger("glimpse_of_thoughts")


def show_preview(post: GeneratedPost, image_path: Path, open_image: bool = True) -> None:
    print("\n" + "=" * 72)
    print("GLIMPSE OF THOUGHTS — PREVIEW")
    print("=" * 72)
    print(f"Image: {image_path}")
    print(f"\nQuote ({post.quote.category}):\n{post.quote.text}")
    if post.quote.author and post.quote.author.lower() != "unknown":
        print(f"— {post.quote.author}")
    print(f"\nCaption:\n{post.caption}")
    print(f"\nHashtags:\n{' '.join(post.hashtags)}")
    print("=" * 72)
    if open_image:
        try:
            with Image.open(image_path) as image:
                ImageShow.show(image, title="Glimpse Of Thoughts preview")
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("Could not open graphical preview: %s", exc)
            print(f"Graphical preview unavailable; inspect the saved image at {image_path}.")
