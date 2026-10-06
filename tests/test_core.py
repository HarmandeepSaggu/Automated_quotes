from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config_loader import load_settings
from hashtag_engine import HashtagEngine
from history_manager import HistoryManager
from image_generator import ImageGenerator
from models import GeneratedPost, Quote
from quote_engine import QuoteEngine


class CoreTestCase(unittest.TestCase):
    def test_quote_engine_skips_used_quote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "quotes").mkdir()
            (root / "quotes" / "quotes.txt").write_text(
                "First quote has a second line.\nStill the same quote.\n\nSecond quote.\n",
                encoding="utf-8",
            )
            config = load_settings(Path(__file__).parents[1] / "config" / "settings.yaml", Path(__file__).parents[1])
            config["quotes"].update({"source": "txt", "text_file": "quotes/quotes.txt"})
            history = HistoryManager(root / "history.json")
            first = QuoteEngine(root, config, history).next_quote()
            history.record(GeneratedPost("2026-01-01", first, "caption", ["#one"], "one.png"))
            second = QuoteEngine(root, config, history).next_quote()
            self.assertEqual(first.text, "First quote has a second line. Still the same quote.")
            self.assertNotEqual(first.normalized(), second.normalized())

    def test_curated_quote_file_has_500_valid_unique_blocks(self) -> None:
        project = Path(__file__).parents[1]
        blocks = (project / "quotes" / "quotes.txt").read_text(encoding="utf-8").strip().split("\n\n")
        self.assertEqual(len(blocks), 500)
        self.assertEqual(len({" ".join(block.split()).casefold() for block in blocks}), 500)
        for block in blocks:
            self.assertEqual(len(block.splitlines()), 1)
            self.assertTrue(20 <= len(block.split()) <= 60)
            self.assertNotIn('"', block)
            self.assertNotIn("|", block)

    def test_hashtags_are_in_requested_range_and_unique(self) -> None:
        tags = HashtagEngine(20).generate(Quote("A calm thought", category="Mindfulness"))
        self.assertEqual(len(tags), 20)
        self.assertEqual(len({tag.lower() for tag in tags}), 20)
        self.assertTrue(all(tag.startswith("#") for tag in tags))

    def test_image_renderer_uses_required_dimensions(self) -> None:
        project = Path(__file__).parents[1]
        settings = load_settings(project / "config" / "settings.yaml", project)
        with tempfile.TemporaryDirectory() as directory:
            target = ImageGenerator(project, settings).render(Quote("A small, steady step."), Path(directory) / "quote.png")
            from PIL import Image
            with Image.open(target) as image:
                self.assertEqual(image.size, (1080, 1350))


if __name__ == "__main__":
    unittest.main()
