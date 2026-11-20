"""District looks task 1: walls per District (zone-generator-district-looks Req 1).

Each room draws its Scales from its own District's Purpose, and leans only on neighbours of its
own District, so a cave District's rooms are mostly ``rough`` and a fortress District's are not,
whichever District comes first. A topology rule's wing keeps its override (archive decision 3):
a fortress's cave wing stays rough and a cave's masonry wing stays built, so those rooms are
left out of the counts.
"""

from collections import Counter

import pytest

import ai.expand as expand
from ai.schema import ZonePlan

SEEDS = range(1, 6)
ORDERS = [("cave", "fortress"), ("fortress", "cave")]
FOREIGN_WING = {"cave": "masonry", "fortress": "cave"}     # the wing whose override a District keeps


def _styles(order):
    """(Purpose, in its foreign wing?) -> Counter of wall styles over the seeds."""
    out = {(p, w): Counter() for p in order for w in (False, True)}
    for seed in SEEDS:
        plan = ZonePlan(name="dl", room_count=16, layout="graph", districts=True,
                        district_plan=[{"purpose": p} for p in order]).validate()
        spec = expand.plan_to_spec(plan, seed=seed)
        assert [d.purpose for d in spec.districts][:2] == list(order)
        purpose = {d.id: d.purpose for d in spec.districts}
        records = spec.layout["rooms"]
        for room in spec.rooms:
            p = purpose[room.district]
            assert room.room_theme == p
            if p in order:
                in_wing = records[room.id].get("wing", "") == FOREIGN_WING[p]
                out[(p, in_wing)][records[room.id]["style"]] += 1
    return out


@pytest.fixture(scope="module", params=ORDERS, ids=lambda o: "_then_".join(o))
def styles(request):
    return _styles(request.param)


def test_cave_district_is_mostly_rough(styles):
    cave = styles[("cave", False)]
    assert cave["rough"] >= 0.7 * sum(cave.values()), dict(cave)


def test_fortress_district_has_no_rough(styles):
    assert styles[("fortress", False)]["rough"] == 0, dict(styles[("fortress", False)])
