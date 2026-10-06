"""Deterministic short-caption generation with optional safe templating."""
from __future__ import annotations

from models import Quote


class CaptionGenerator:
    _templates = {
        "Life": "A quiet reminder to notice the life already unfolding.",
        "Self Growth": "Keep becoming, one honest step at a time.",
        "Motivation": "Let consistency carry you further than urgency.",
        "Sikh Wisdom": "Let courage, humility, and service guide the day.",
        "Discipline": "Small promises kept daily become a life of strength.",
        "Success": "Build quietly. Let the work speak when it is ready.",
        "Relationships": "The things we feel deeply are often the things worth tending.",
        "Stoicism": "Return to what is within your care, and begin there.",
        "Mindfulness": "Make room for this moment; it is the one you have.",
    }

    def generate(self, quote: Quote) -> str:
        return self._templates.get(quote.category, self._templates["Life"])
