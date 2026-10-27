"""
ai/planner.py
-------------
Top-level planner: turn a prompt into a ZoneSpec.

Provider selection mirrors the texture system:
  - LLMPlanner if an API key is present (and it succeeds)
  - RulePlanner otherwise (always works, no network)

The factory grounds the LLM with a style hint derived from the measured style
profile, validates the resulting plan, and falls back to the rule planner on
any failure so planning never breaks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core.env import env_value
from generators.zone_spec import ZoneSpec
from .schema import ZonePlan
from .rule_planner import RulePlanner
from .llm_planner import LLMPlanner
from .expand import plan_to_spec

_forced = None  # test override


def _redacted_error(exc: Exception) -> str:
    """Describe an exception without leaking a key, URL or response body.

    LLM SDK exceptions (``openai``/``anthropic``) stringify to the request URL
    and the response body, which can echo the prompt or an auth header. We log
    only the exception TYPE and, if the SDK attached one, the HTTP status code —
    never ``str(exc)``.
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status is not None:
        return f"{type(exc).__name__} (HTTP {status})"
    return type(exc).__name__


def get_planner(prefer_llm: bool = True):
    """Return the best available planner."""
    if _forced is not None:
        return _forced
    override = (env_value("EQ_S3D_PLANNER") or "").lower()
    if override == "rule":
        return RulePlanner()
    if override == "llm":
        return LLMPlanner()
    if prefer_llm:
        llm = LLMPlanner()
        if llm.available():
            return llm
    return RulePlanner()


def set_planner(planner) -> None:
    """Force a planner (tests). None restores auto-select."""
    global _forced
    _forced = planner


def make_plan(prompt: str, name: str = "zone") -> ZonePlan:
    """Produce a validated ZonePlan from a prompt, with fallback."""
    planner = get_planner()
    try:
        if planner.name == "llm":
            hint = _style_hint_for(prompt)
            return planner.plan(prompt, name=name, style_hint=hint)
        return planner.plan(prompt, name=name)
    except Exception as e:
        if planner.name != "rule":
            print(f"[planner] {planner.name} failed ({_redacted_error(e)}); "
                  f"falling back to rule planner")
            return RulePlanner().plan(prompt, name=name)
        raise


def plan_zone(prompt: str, name: str = "zone",
              seed: Optional[int] = None) -> tuple[ZonePlan, ZoneSpec]:
    """
    Full pipeline: prompt → ZonePlan → ZoneSpec.
    Returns both so callers can report what the planner decided.
    """
    plan = make_plan(prompt, name=name)
    spec = plan_to_spec(plan, seed=seed)
    return plan, spec


# ---------------------------------------------------------------------------
# Style grounding
# ---------------------------------------------------------------------------

def _style_hint_for(prompt: str) -> str:
    """
    Build a short style-guidance string from the matching profile so the LLM's
    size/room choices stay near real-EQ proportions. We don't know the theme
    yet, so include a brief summary of each available profile.
    """
    styles_dir = Path(__file__).parent.parent / "styles"
    if not styles_dir.exists():
        return ""
    lines = []
    for p in sorted(styles_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        theme = d.get("theme", p.stem)
        geo = d.get("geometry", {})
        mats = d.get("materials", {}).get("count", {})
        ceil = geo.get("ceiling_height", {})
        lines.append(
            f"- {theme}: ceiling {ceil.get('min', '?')}-{ceil.get('max', '?')}u "
            f"(typical {ceil.get('mean', '?')}), materials ~{mats.get('mean', '?')}"
        )
    return "Real EQ zone proportions by theme:\n" + "\n".join(lines) if lines else ""
