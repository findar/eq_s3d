"""
eq_s3d.ai — natural-language planning.

Turns a text prompt into a ZoneSpec via a planner (rule-based default, LLM
drop-in), reusing the same generators the dropdowns drive.

Public API:
    plan_zone(prompt, name, seed) -> (ZonePlan, ZoneSpec)
    make_plan(prompt, name)       -> ZonePlan
    get_planner()                 -> the active planner
"""

from .planner import plan_zone, make_plan, get_planner, set_planner
from .schema import ZonePlan
from .expand import plan_to_spec

__all__ = [
    "plan_zone",
    "make_plan",
    "get_planner",
    "set_planner",
    "ZonePlan",
    "plan_to_spec",
]
