"""Pixel-measured paragraph layout, independent of source-file line breaks."""
from __future__ import annotations

from functools import lru_cache
import re

from PIL import ImageFont


class TextLayoutError(ValueError):
    """Content cannot fit the editorial region without clipping or truncation."""


def normalize_paragraph(text: str) -> str:
    """Keep wording/punctuation intact; source newlines are whitespace, not layout."""
    return " ".join(text.replace("\ufeff", "").split())


def measured_width(text: str, font: ImageFont.FreeTypeFont) -> float:
    left, _, right, _ = font.getbbox(text, anchor="ls")
    # Account for italic overhang as well as the typographic advance.
    return max(float(right), font.getlength(text)) - min(0, left)


def wrap_paragraph(
    text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int = 4,
) -> list[str]:
    """Use the fewest feasible lines, then favor balanced widths and natural pauses.

    8–15 words is a soft readability preference, never a forced break interval.
    Sentence/clause punctuation is preferred where physical width permits it.
    Short quotes remain one line; words are never split, elided, or rewritten.
    """
    words = normalize_paragraph(text).split()
    if not words:
        raise TextLayoutError("Cannot render an empty quote")
    if width <= 0 or not 1 <= max_lines <= 4:
        raise TextLayoutError("Quote width must be positive and max_lines must be 1–4")
    if len(words) > 160:
        raise TextLayoutError("Quote is too long for a compact editorial card; shorten the text")

    # Cache candidate fragments once rather than measuring them in every DP state.
    fragments: dict[tuple[int, int], tuple[str, float]] = {}
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            fragment = " ".join(words[start:end])
            length = measured_width(fragment, font)
            if length > width:
                break
            fragments[start, end] = fragment, length
        if (start, start + 1) not in fragments:
            raise TextLayoutError("Quote contains a word wider than the configured quote area")

    weak_endings = {"a", "an", "the", "of", "to", "in", "at", "for", "with", "your", "my", "their"}
    clause_starts = {"but", "because", "while", "although", "unless", "when", "and", "without"}

    def line_cost(start: int, end: int, length: float) -> float:
        count = end - start
        cost = 4.0 * (1.0 - length / width) ** 2
        cost += 0.06 * max(0, 8 - count) ** 2 + 0.02 * max(0, count - 15) ** 2
        if count < 3 and len(words) > 6:
            cost += 4.0  # Avoid stranded one-/two-word tails.
        if end < len(words):
            tail = words[end - 1].rstrip('\"\u201d\u2019)')
            if re.search(r"[.!?]$", tail):
                cost -= 0.55
            elif tail.endswith((";", ":", ",", "—")):
                cost -= 0.30
            elif words[end].lower().strip(",;:") in clause_starts:
                cost -= 0.15
            if tail.lower() in weak_endings:
                cost += 0.6
        return cost

    @lru_cache(maxsize=None)
    def best(start: int, remaining: int) -> tuple[float, tuple[str, ...]] | None:
        if remaining == 0:
            return (0.0, ()) if start == len(words) else None
        if len(words) - start < remaining:
            return None
        answer = None
        for end in range(start + 1, len(words) - remaining + 2):
            fragment = fragments.get((start, end))
            if fragment is None:
                break
            rest = best(end, remaining - 1)
            if rest is None:
                continue
            line, length = fragment
            candidate = line_cost(start, end, length) + rest[0], (line,) + rest[1]
            if answer is None or candidate[0] < answer[0]:
                answer = candidate
        return answer

    for count in range(1, max_lines + 1):
        result = best(0, count)
        if result is not None:
            return list(result[1])
    raise TextLayoutError(f"Quote needs more than {max_lines} lines at this font size")
