"""Quote selection from local files or OpenAI with duplicate protection."""
from __future__ import annotations

import csv
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import requests

from config_loader import resolve_path
from history_manager import HistoryManager
from models import Quote
from text_layout import normalize_paragraph

LOGGER = logging.getLogger("glimpse_of_thoughts")


class QuoteError(RuntimeError):
    """Raised when no valid unused quote can be selected."""


class QuoteEngine:
    def __init__(self, root: Path, settings: dict[str, Any], history: HistoryManager):
        self.root = root
        self.settings = settings
        self.history = history
        self.quotes_config = settings["quotes"]
        self.used = history.used_quotes()

    @staticmethod
    def _clean(value: Any, fallback: str) -> str:
        value = "" if value is None else str(value)
        return " ".join(value.replace("\ufeff", "").split()).strip() or fallback

    @staticmethod
    def _clean_quote(value: Any) -> str:
        return normalize_paragraph("" if value is None else str(value))

    def _valid(self, quote: Quote) -> bool:
        return bool(quote.text.strip()) and quote.normalized() not in self.used

    def _load_txt(self) -> list[Quote]:
        """Load blank-separated quote blocks while retaining legacy pipe support."""
        path = resolve_path(self.root, self.quotes_config["text_file"])
        if not path.exists():
            raise QuoteError(f"Quote text file not found: {path}")
        result: list[Quote] = []
        content = path.read_text(encoding="utf-8-sig")
        blocks = re.split(r"\n\s*\n", content)
        for block_number, raw_block in enumerate(blocks, 1):
            lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
            if not lines or all(line.startswith("#") for line in lines):
                continue
            # Legacy one-line `text | author | category` records remain supported.
            if len(lines) == 1 and "|" in lines[0]:
                parts = [part.strip() for part in lines[0].split("|")]
                text = self._clean_quote(parts[0])
                author = parts[1] if len(parts) > 1 and parts[1] else "Unknown"
                category = parts[2] if len(parts) > 2 and parts[2] else "Life"
            else:
                text = self._clean_quote(" ".join(lines))
                author = "Unknown"
                category = "Life"
            if not text:
                LOGGER.warning("Ignoring empty quote block %s in %s", block_number, path)
                continue
            result.append(Quote(text, author, category))
        return result

    def _load_csv(self) -> list[Quote]:
        path = resolve_path(self.root, self.quotes_config["csv_file"])
        if not path.exists():
            raise QuoteError(f"Quote CSV file not found: {path}")
        result: list[Quote] = []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                required = {"quote", "author", "category"}
                if not reader.fieldnames or not required.issubset({f.strip().lower() for f in reader.fieldnames}):
                    raise QuoteError(f"{path} must contain columns: quote, author, category")
                for line_number, row in enumerate(reader, 2):
                    normalized = {str(k).strip().lower(): v for k, v in row.items()}
                    text = self._clean(normalized.get("quote"), "")
                    if not text:
                        LOGGER.warning("Ignoring empty quote at %s:%d", path, line_number)
                        continue
                    result.append(Quote(text, self._clean(normalized.get("author"), "Unknown"), self._clean(normalized.get("category"), "Life")))
        except (OSError, csv.Error) as exc:
            raise QuoteError(f"Cannot read {path}: {exc}") from exc
        return result

    def _generate_ai(self) -> Quote:
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise QuoteError("OPENAI_API_KEY is required for AI quote generation")
        categories = ", ".join(self.quotes_config.get("categories", []))
        prompt = (
            "Write one original quote that feels like a precise observation about modern life, human behavior, "
            "psychology, discipline, relationships, loneliness, regret, failure, or personal growth. "
            "It must feel emotionally intelligent, human, memorable, and slightly uncomfortable in a truthful way. "
            "Write 20 to 35 words in simple English using proper, complete sentences. "
            "Use natural sentence flow: one compact prose paragraph, with no manual line breaks. "
            "These should feel like real thoughts, not poetry or vertically stretched motivational content. "
            "Do not break phrases into groups of 3 to 5 words. The renderer handles a maximum of "
            "2 to 4 visually balanced lines, aiming for 8 to 15 words per line where space permits. "
            "Avoid cliches, generic motivation, advice, commands, emojis, quotation marks, and famous phrasing. "
            f"Choose one category from: {categories}. Return JSON only with keys quote and category; "
            'author must be omitted or "Unknown".'
        )
        endpoint = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.settings["openai"].get("model", "gpt-4o-mini"),
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You produce safe, original editorial writing."},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=int(self.settings["openai"].get("timeout_seconds", 30)),
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
            if not isinstance(parsed, dict) or not isinstance(parsed.get("quote"), str):
                raise ValueError("Expected a JSON object with a quote string")
            quote = Quote(
                self._clean_quote(parsed.get("quote")),
                "Unknown",
                self._clean(parsed.get("category"), "Life"),
                "openai",
            )
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise QuoteError(f"OpenAI quote generation failed: {exc}") from exc
        if not quote.text:
            raise QuoteError("OpenAI returned an empty quote")
        if not 20 <= len(quote.text.split()) <= 60:
            raise QuoteError("OpenAI quote must contain 20–60 words; prefer 20–35 for a compact card")
        return quote

    def next_quote(self) -> Quote:
        source = str(self.quotes_config.get("source", "auto")).lower()
        candidates: list[Quote] = []
        if source in {"auto", "txt"}:
            try:
                candidates.extend(self._load_txt())
            except QuoteError:
                if source == "txt":
                    raise
        if source in {"auto", "csv"}:
            try:
                candidates.extend(self._load_csv())
            except QuoteError:
                if source == "csv":
                    raise

        for quote in candidates:
            if self._valid(quote) and self.history.reserve_quote(quote):
                self.used.add(quote.normalized())
                return quote
        if source in {"ai", "auto"}:
            for _ in range(3):
                quote = self._generate_ai()
                if self._valid(quote) and self.history.reserve_quote(quote):
                    self.used.add(quote.normalized())
                    return quote
            raise QuoteError("AI returned only duplicate quotes")
        raise QuoteError("No unused quotes remain in the configured source")
