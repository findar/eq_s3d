"""
ai/rule_planner.py
------------------
Rule-based (no-API) prompt planner. Parses a natural-language prompt with
keyword heuristics into a ZonePlan. This is the DEFAULT planner — it runs with
no API key, deterministically, and makes the prompt box genuinely responsive
even offline.

It won't match an LLM's nuance, but "a big flooded cave with lots of chambers"
should reliably produce a large cave with a water region and a high room count.
"""

from __future__ import annotations

import re
from typing import List

from .schema import ZonePlan


# Keyword → theme
_THEME_WORDS = {
    "cave": ["cave", "cavern", "grotto", "tunnel", "underground", "mine"],
    "outdoor": ["outdoor", "forest", "field", "meadow", "hills", "plains",
                "valley", "mountain", "wilderness", "swamp", "desert", "coast"],
    "city": ["city", "town", "village", "market", "bazaar", "streets", "plaza"],
    "dungeon": ["dungeon", "crypt", "catacomb", "ruin", "temple", "keep",
                "fortress", "lair", "stronghold", "vault"],
}

# Keyword → region kind
_REGION_WORDS = {
    "water": ["water", "flooded", "lake", "pool", "pond", "river", "underwater",
              "aquatic", "sea", "ocean", "wet"],
    "lava": ["lava", "magma", "volcanic", "molten", "fire", "volcano"],
    "ice": ["ice", "frozen", "frost", "glacier", "icy", "snow"],
}

_SIZE_WORDS = {
    "huge": ["huge", "massive", "enormous", "vast", "sprawling", "gigantic"],
    "large": ["large", "big", "grand", "expansive", "spacious"],
    "small": ["small", "tiny", "cramped", "cozy", "little", "compact"],
}

# Words implying a keyed / gated dungeon
_GATED_WORDS = ["locked", "key", "keyed", "sealed", "gated", "vault", "secured",
                "barred", "warded", "sanctum", "forbidden"]

_VERTICALITY_WORDS = {
    "dramatic": ["towering", "vertical", "multi-level", "multilevel", "layered",
                 "steep", "cliffs", "tiered", "stacked"],
    "flat": ["flat", "level", "single-level", "ground-level", "even"],
}

# Rough room-count hints
_MANY_WORDS = ["many", "lots", "numerous", "maze", "labyrinth", "sprawling", "warren"]
_FEW_WORDS = ["few", "couple", "single", "one big", "simple"]

# size → base room count and footprint multiplier
_SIZE_ROOMS = {"small": 3, "medium": 5, "large": 8, "huge": 14}


class RulePlanner:
    name = "rule"

    def available(self) -> bool:
        return True

    def plan(self, prompt: str, name: str = "zone") -> ZonePlan:
        text = (prompt or "").lower()

        theme = self._match_theme(text)
        size = self._match_one(text, _SIZE_WORDS, default="medium")
        verticality = self._match_one(text, _VERTICALITY_WORDS, default="moderate")
        regions = self._match_regions(text)
        room_count = self._room_count(text, size)
        elevation = verticality != "flat"
        mood = self._extract_mood(text)
        locks = self._lock_count(text, room_count)

        return ZonePlan(
            name=name,
            theme=theme,
            room_count=room_count,
            size=size,
            elevation=elevation,
            verticality=verticality,
            regions=regions,
            locks=locks,
            mood=mood,
            prompt=prompt or "",
        ).validate()

    # ------------------------------------------------------------------

    def _match_theme(self, text: str) -> str:
        # Score each theme by keyword hits; default dungeon.
        best, best_score = "dungeon", 0
        for theme, words in _THEME_WORDS.items():
            score = sum(text.count(w) for w in words)
            if score > best_score:
                best, best_score = theme, score
        return best

    def _match_one(self, text: str, mapping: dict, default: str) -> str:
        for value, words in mapping.items():
            if any(w in text for w in words):
                return value
        return default

    def _match_regions(self, text: str) -> List[str]:
        found = []
        for kind, words in _REGION_WORDS.items():
            if any(w in text for w in words):
                found.append(kind)
        return found

    def _room_count(self, text: str, size: str) -> int:
        # Explicit number in the prompt wins ("5 rooms", "three chambers")
        n = _explicit_count(text)
        if n is not None:
            return max(1, min(30, n))

        base = _SIZE_ROOMS.get(size, 5)
        if any(w in text for w in _MANY_WORDS):
            base = int(base * 1.8)
        elif any(w in text for w in _FEW_WORDS):
            base = max(2, int(base * 0.5))
        return max(1, min(30, base))

    def _lock_count(self, text: str, room_count: int) -> int:
        """
        Infer the number of locked gates from the prompt. A keyed/sealed/
        vaulted dungeon gets 1–2 locks scaled to its size; otherwise open (0).
        An explicit number ("two locked doors") wins.
        """
        if not any(w in text for w in _GATED_WORDS):
            return 0
        import re
        # Explicit digit: "2 locked doors"
        m = re.search(r"(\d+)\s+(?:locked|keyed|sealed|key)", text)
        if m:
            return max(1, min(5, int(m.group(1))))
        # Explicit word number: "two locked doors"
        for word, num in _WORD_NUMBERS.items():
            if re.search(rf"\b{word}\s+(?:locked|keyed|sealed|key)", text):
                return max(1, min(5, num))
        # Otherwise 1 lock for small zones, 2 for larger keyed dungeons.
        return 2 if room_count >= 10 else 1

    def _extract_mood(self, text: str) -> str:
        mood_words = ["dark", "damp", "gloomy", "bright", "ancient", "ruined",
                      "overgrown", "icy", "fiery", "eerie", "sacred", "cursed",
                      "misty", "foggy", "mossy", "crumbling"]
        found = [w for w in mood_words if w in text]
        return ", ".join(found[:4])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "fifteen": 15, "twenty": 20,
}

_COUNT_NOUNS = r"(?:rooms?|chambers?|caverns?|clearings?|halls?|areas?)"


def _explicit_count(text: str) -> int:
    # Digit form: "5 rooms", "12 chambers"
    m = re.search(rf"(\d+)\s+{_COUNT_NOUNS}", text)
    if m:
        return int(m.group(1))
    # Word form: "three chambers"
    for word, num in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\s+{_COUNT_NOUNS}", text):
            return num
    return None
