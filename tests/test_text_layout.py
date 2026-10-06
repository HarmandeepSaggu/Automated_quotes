"""Regression coverage for paragraph generation and compact editorial rendering."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageChops, ImageDraw, ImageFont

from config_loader import ConfigurationError, load_settings, validate_settings
from history_manager import HistoryManager
from image_generator import ImageGenerationError, ImageGenerator
from models import GeneratedPost, Quote
from quote_engine import QuoteEngine, QuoteError
from text_layout import measured_width, normalize_paragraph, wrap_paragraph

ROOT = Path(__file__).parents[1]


class TextLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(ROOT / "config/settings.yaml", ROOT)
        cls.generator = ImageGenerator(ROOT, cls.settings)

    def test_old_short_lines_and_paragraph_have_identical_layout(self) -> None:
        old = "Most people aren't tired from work.\nThey're tired from carrying thoughts\nthey never speak about."
        prose = normalize_paragraph(old)
        before = self.generator.layout_quote(old)
        after = self.generator.layout_quote(prose)
        self.assertEqual(before.lines, after.lines)
        self.assertEqual(before.font_size, after.font_size)
        self.assertEqual(" ".join(after.lines), prose)
        self.assertLessEqual(len(after.lines), 4)
        self.assertTrue(all(len(line.split()) >= 3 for line in after.lines))

    def test_natural_sentence_break_is_preferred_when_it_fits(self) -> None:
        font = ImageFont.load_default(size=36)
        first = "You can miss someone without wanting that relationship back."
        second = "Missing is a feeling, not a reason to return."
        width = int(max(measured_width(first, font), measured_width(second, font))) + 1
        self.assertEqual(wrap_paragraph(first + " " + second, font, width), [first, second])

    def test_short_quote_is_not_stretched(self) -> None:
        result = self.generator.layout_quote("An ordinary afternoon.")
        self.assertEqual(result.lines, ("An ordinary afternoon.",))

    def test_full_corpus_fits_and_preserves_content(self) -> None:
        paragraphs = (ROOT / "quotes/quotes.txt").read_text(encoding="utf-8").strip().split("\n\n")
        area = self.settings["image"]["quote"]
        sizes = Counter()
        for number, paragraph in enumerate(paragraphs, 1):
            with self.subTest(quote=number):
                layout = self.generator.layout_quote(paragraph)
                self.assertTrue(2 <= len(layout.lines) <= area["max_lines"])
                self.assertEqual(" ".join(layout.lines), normalize_paragraph(paragraph))
                self.assertLessEqual(layout.height, area["max_height"])
                self.assertGreaterEqual(layout.font_size, self.settings["image"]["min_font_size"])
                sizes[layout.font_size] += 1
                for index, line in enumerate(layout.lines):
                    self.assertLessEqual(measured_width(line, layout.font), area["width"])
                    self.assertGreater(len(line.split()), 1)  # No dangling single words.
                    left, top, right, bottom = layout.font.getbbox(line, anchor="ls")
                    baseline = area["y"] + layout.baseline_offset + index * layout.line_step
                    self.assertGreaterEqual(area["x"] + layout.left_offset + left, area["x"])
                    self.assertLessEqual(layout.left_offset + right, area["width"])
                    self.assertGreaterEqual(baseline + top, area["y"])
                    self.assertLessEqual(baseline + bottom, area["y"] + area["max_height"])
                self.assertLess(area["y"] + layout.height, self.settings["image"]["signature"]["y"] - 40)
        self.assertEqual(sum(sizes.values()), 500)

    def test_true_baseline_spacing_and_ink_bounds(self) -> None:
        text = " ".join(["Quiet decisions change ordinary lives."] * 4)
        layout = self.generator.layout_quote(text)
        area = self.settings["image"]["quote"]
        self.assertEqual(layout.line_step, round(layout.font_size * self.settings["image"]["line_height"]))
        canvas = Image.new("RGB", (1080, 1350), "white")
        draw = ImageDraw.Draw(canvas)
        for index, line in enumerate(layout.lines):
            draw.text((area["x"] + layout.left_offset,
                       area["y"] + layout.baseline_offset + index * layout.line_step),
                      line, font=layout.font, fill="black", anchor="ls")
        bbox = ImageChops.difference(canvas, Image.new("RGB", canvas.size, "white")).getbbox()
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(bbox[0], area["x"])
        self.assertLessEqual(bbox[2], area["x"] + area["width"])
        self.assertGreaterEqual(bbox[1], area["y"])
        self.assertLessEqual(bbox[3], area["y"] + layout.height)

    def test_oversized_content_errors_without_creating_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "invalid.png"
            for text in ("", "W" * 200, "An ordinary thought. " * 80):
                with self.subTest(text=text[:20]), self.assertRaises(ImageGenerationError):
                    self.generator.render(Quote(text), target)
                self.assertFalse(target.exists())

    def test_vertical_limit_is_enforced(self) -> None:
        settings = deepcopy(self.settings)
        settings["image"]["quote"]["max_height"] = 10
        with self.assertRaisesRegex(ImageGenerationError, "cannot fit"):
            ImageGenerator(ROOT, settings).layout_quote("A paragraph cannot be squeezed into ten pixels.")

    def test_missing_font_fallback_keeps_requested_size(self) -> None:
        generator = ImageGenerator(ROOT, self.settings)
        with patch.object(generator, "_font_candidates", return_value=iter(())):
            font = generator._load_font(36)
        self.assertEqual(font.size, 36)
        self.assertGreater(measured_width("Readable fallback font", font), 200)

    def test_invalid_geometry_and_line_height_are_rejected(self) -> None:
        changes = [
            ("quote", "width", 0), ("quote", "width", 1200),
            ("quote", "x", 2000), ("quote", "x", True),
            ("quote", "max_lines", 5), ("quote", "max_lines", 0),
            ("quote", "max_height", 900), ("quote", "max_height", 0),
            ("image", "min_font_size", 50), ("image", "width", True),
            ("image", "line_height", float("nan")),
            ("image", "line_height", float("inf")),
            ("image", "line_height", 0.5),
        ]
        for section, key, value in changes:
            with self.subTest(section=section, key=key, value=value):
                settings = deepcopy(self.settings)
                target = settings["image"] if section == "image" else settings["image"][section]
                target[key] = value
                with self.assertRaises(ConfigurationError):
                    validate_settings(settings)


class QuoteProseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = load_settings(ROOT / "config/settings.yaml", ROOT)
        self.history = HistoryManager(self.root / "history.json")
        self.engine = QuoteEngine(self.root, self.settings, self.history)

    def test_legacy_wrapped_text_is_a_single_thought(self) -> None:
        path = self.root / "quotes/quotes.txt"
        path.parent.mkdir()
        path.write_text("A thought\nthat continues naturally.\n\nAnother thought. | Unknown | Life\n", encoding="utf-8")
        quotes = self.engine._load_txt()
        self.assertEqual([quote.text for quote in quotes], ["A thought that continues naturally.", "Another thought."])

    def test_newline_changes_cannot_bypass_history(self) -> None:
        quote = Quote("The same\nthought still matters.")
        self.history.record(GeneratedPost("2026-01-01", quote, "caption", [], "x.png"))
        self.assertTrue(self.history.is_used(Quote("The same thought still matters.")))

    def test_csv_multiline_text_is_reflowed(self) -> None:
        import csv
        path = self.root / "quotes/quotes.csv"
        path.parent.mkdir()
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["quote", "author", "category"])
            writer.writerow(["A thought\ncontinued here.", "Unknown", "Life"])
        self.assertEqual(self.engine._load_csv()[0].text, "A thought continued here.")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only-key"})
    @patch("quote_engine.requests.post")
    def test_ai_prompt_and_response_use_natural_prose(self, post: Mock) -> None:
        text = ("You can want a better life\nand still resent how much of this one\n"
                "you have to spend preparing for it.\nBoth feelings can be honest.")
        post.return_value.json.return_value = {"choices": [{"message": {"content": json.dumps({"quote": text, "category": "Life"})}}]}
        quote = self.engine._generate_ai()
        self.assertEqual(quote.text, normalize_paragraph(text))
        self.assertEqual(quote.author, "Unknown")
        prompt = post.call_args.kwargs["json"]["messages"][1]["content"]
        self.assertIn("no manual line breaks", prompt)
        self.assertNotIn("2 to 5 short lines", prompt)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only-key"})
    @patch("quote_engine.requests.post")
    def test_invalid_ai_shape_and_length_are_rejected(self, post: Mock) -> None:
        for body in ([], {"quote": ["not prose"]}, {"quote": "Too short."}, {"quote": "word " * 61}):
            with self.subTest(body=body):
                post.return_value.json.return_value = {"choices": [{"message": {"content": json.dumps(body)}}]}
                with self.assertRaises(QuoteError):
                    self.engine._generate_ai()


if __name__ == "__main__":
    unittest.main()
