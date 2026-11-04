"""
tests/test_topology_levels.py
-----------------------------
Dungeon verticality task 4 (Requirements 4.1, 4.2; design "Levels",
"Stacking"): Levels in the graph engine.

Goldens: sha256 of the Zone_Spec JSON for pinned graph builds, captured on
the step 6 code BEFORE Levels landed. Levels must not move a build that
doesn't stack. A mismatch is a regression, never a reason to recapture
(rule out a numpy/scipy bump first, as ``tests/test_layout_engine.py`` says).
"""

from __future__ import annotations

import hashlib
import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan


def _spec_hash(spec) -> str:
    return hashlib.sha256(
        json.dumps(spec.to_dict(), sort_keys=True).encode()).hexdigest()


# label -> (ZonePlan fields, seed, Zone_Spec sha256). Graph engine (the default
# layout), the shipped rule sets as the themes and races pick them.
GOLDENS = {
    # Three "below" edges (the shipped passage rule).
    "classic_eq": (dict(zone_type="dungeon", room_count=12, layout="graph"), 2,
                   "cd96fa096171ac02ef38cfb1ddfb0ffddc1a69f10223b7dfc755286786b7bf13"),
    # One "below" edge (the shipped tunnel rule).
    "warren": (dict(zone_type="dungeon", room_count=12, layout="graph",
                    rule_set="warren"), 2,
               "61f3b588a6a5737a3004c49d607f83947a7601ffe314386ef9195ab73106c77d"),
    "temple": (dict(zone_type="dungeon", room_count=10, layout="graph",
                    dungeon_theme="temple", verticality="dramatic"), 3,
               "1e37db5eb23657f20015c0b6b0e08dfb7939f8c9352fa283afbfe2175bf002fe"),
    "ogre": (dict(zone_type="dungeon", room_count=9, layout="graph",
                  dungeon_race="ogre", locks=1), 21,
             "5f1cfecfa159b7f6fec58a55f7e3675b89b9da276b14fbc6ce757d65941790ec"),
}


@pytest.mark.parametrize("label", sorted(GOLDENS))
def test_graph_build_matches_step6_golden(label):
    fields, seed, golden = GOLDENS[label]
    spec = plan_to_spec(ZonePlan(name=f"lv_{label}", **fields).validate(), seed=seed)
    assert _spec_hash(spec) == golden, "graph-engine Zone_Spec changed"
