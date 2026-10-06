"""Curated, deterministic hashtag selection."""
from __future__ import annotations

import hashlib
import re

from models import Quote


class HashtagEngine:
    _groups = {
        "niche": [
            "#glimpseofthoughts", "#quietwisdom", "#editorialquotes", "#thoughtfulwords",
            "#mindfulwriting", "#dailyreflection", "#innerstillness", "#softstrength",
        ],
        "medium": [
            "#deepquotes", "#selfgrowthjourney", "#intentional living", "#mindsetshift",
            "#disciplineequalsfreedom", "#meaningfullife", "#reflectivewriting", "#modernwisdom",
            "#quotesdaily", "#lifeinwords",
        ],
        "broad": [
            "#quotes", "#inspiration", "#motivation", "#mindfulness", "#success",
            "#love", "#life", "#wisdom", "#positivity", "#growth",
        ],
    }

    def __init__(self, count: int = 20):
        if not 15 <= count <= 25:
            raise ValueError("Hashtag count must be between 15 and 25")
        self.count = count

    @staticmethod
    def _valid(tag: str) -> str:
        tag = tag.replace(" ", "")
        tag = re.sub(r"[^#\w]", "", tag, flags=re.UNICODE)
        return tag if tag.startswith("#") else f"#{tag}"

    def generate(self, quote: Quote) -> list[str]:
        seed = int(hashlib.sha256(quote.normalized().encode("utf-8")).hexdigest(), 16)
        selected: list[str] = []
        # Round-robin keeps the result balanced across niche, medium, and broad reach.
        pools = [list(values) for values in self._groups.values()]
        for index, pool in enumerate(pools):
            offset = (seed >> (index * 8)) % len(pool)
            pool[:] = pool[offset:] + pool[:offset]
        cursor = 0
        while len(selected) < self.count:
            pool = pools[cursor % len(pools)]
            for candidate in pool:
                candidate = self._valid(candidate)
                if candidate.lower() not in {item.lower() for item in selected}:
                    selected.append(candidate)
                    break
            cursor += 1
            if cursor > self.count * 4:
                break
        return selected[: self.count]
