"""
ai/llm_planner.py
-----------------
LLM-backed prompt planner. Asks an LLM to fill the ZonePlan JSON schema from a
natural-language prompt, grounded in the measured style profile so choices stay
within real-EQ bounds.

Provider-abstracted: OpenAI or Anthropic, selected by whichever key is present.
Activates only when a key exists; otherwise `available()` is False and the
factory uses the rule-based planner. Any failure (missing lib, bad JSON, network
error) raises so the factory can fall back.
"""

from __future__ import annotations

import json
from typing import Optional

from core.env import env_value
from .schema import (
    ZonePlan, ZONE_PLAN_JSON_SCHEMA, VALID_DISTRICT_RELATIONSHIPS, VALID_DUNGEON_THEMES,
    VALID_ZONE_TYPES,
)


_SYSTEM_PROMPT = """You are a level designer for EverQuest-style zones.
Given a short description, produce a compact JSON plan for one zone.

Rules:
- Choose exactly one zone_type from: {zone_types}.
- room_count is how many distinct rooms/chambers/clearings (1-30).
- size is the overall footprint: small, medium, large, or huge.
- Set elevation true if the zone should have multiple vertical levels.
- verticality: flat, moderate, or dramatic.
- regions: list any special volumes implied by the description
  (water, lava, ice, pvp, zoneline, generic). Empty if none.
- mood: a short atmosphere note (e.g. "dark and damp").
- districts: true only for a dungeon whose description names 2-3 contrasting
  areas ("the living and the dead", "two factions", "upper and lower halls",
  "a temple fallen to the dead", "overrun by kobolds"); omit it otherwise.
- district_plan: with districts, one object per named area, the entrance's
  area first: {{"purpose": <one of {purposes}, or "" when the words name
  none>}}. The same purpose in every entry gives every area that purpose.
- district_relationship: with districts, one of {relationships}
  (abandoned_vs_active: the areas past the entrance's have fallen or been
  overrun). With districts, room_count is at least 8 (3 areas: 14).

Respond with ONLY the JSON object, no prose.
Honour real-EQ proportions provided in the style guidance.
"""


def system_prompt() -> str:
    """The planner's system prompt, the vocabularies filled in."""
    return _SYSTEM_PROMPT.format(
        zone_types=", ".join(VALID_ZONE_TYPES),
        purposes=", ".join(VALID_DUNGEON_THEMES),
        relationships=", ".join(VALID_DISTRICT_RELATIONSHIPS))


class LLMPlanner:
    name = "llm"

    def __init__(self):
        self.openai_key = env_value("OPENAI_API_KEY")
        self.anthropic_key = env_value("ANTHROPIC_API_KEY")

    def available(self) -> bool:
        return bool(self.openai_key or self.anthropic_key)

    def plan(self, prompt: str, name: str = "zone",
             style_hint: str = "") -> ZonePlan:
        system = system_prompt()
        if style_hint:
            system += f"\nStyle guidance:\n{style_hint}\n"

        if self.openai_key:
            data = self._call_openai(system, prompt)
        elif self.anthropic_key:
            data = self._call_anthropic(system, prompt)
        else:
            raise RuntimeError("No LLM API key available")

        plan = ZonePlan.from_dict(data)
        plan.name = name
        plan.prompt = prompt
        return plan.validate()

    # ------------------------------------------------------------------

    def _call_openai(self, system: str, prompt: str) -> dict:
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
        return json.loads(resp.choices[0].message.content)

    def _call_anthropic(self, system: str, prompt: str) -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=self.anthropic_key)
        resp = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=512,
            system=system + "\nReturn only a JSON object.",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        text = resp.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):text.rfind("}") + 1]
        return json.loads(text)
