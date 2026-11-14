"""Site-sockets task 3 (Req 2.2-2.5; design P2, P3): the World's point Site Sockets.

On the World corpus's landscapes (recorded wilderness and outdoor-dungeon Worlds) and a few
made fresh, ``site_points`` offers points on Site-eligible ground whose Free radii are true by
placement's own ``disc_on_eligible``, in Groups inside the biome's ``gap`` and ``within``,
Groups ``spacing`` apart (spares over the hill excepted among themselves), as many as the
Dense control could ask for twice over, the same for the same inputs, and reading no Sites
control.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from generators.sites import points as pts
from generators.sites.placement import CLEAR_WIDTH, _terrain
from generators.sites.rules import SiteRules, load_sites
from generators.vegetation.placement import Ground
from generators.world import load, world_for

ROOT = Path(__file__).resolve().parent.parent
WORLDS = ROOT / "tests" / "fixtures" / "worlds"
LANDSCAPES = ("wilderness_plains", "wilderness_river", "outdoor_n", "outdoor_s", "outdoor_e",
              "outdoor_w", "outdoor_river")
RULES = load_sites()


def _hill(world):
    hills = [s for s in world.sockets if s.kind == "hillside"]
    return hills[0].ground["footprint"] if hills else None


def _points(world, rules=RULES):
    return pts.site_points(world.terrain, world.spawn, world.recipe["seed"],
                           world.recipe["biome"], rules, hill=_hill(world))


def _text(points) -> str:
    return json.dumps([{"id": p.id, "x": p.x, "y": p.y, "z": p.z, **p.ground()} for p in points])


@pytest.fixture(scope="module", params=LANDSCAPES)
def case(request):
    world = load(WORLDS / f"{request.param}.json")
    return world, _points(world)


@pytest.fixture(scope="module", params=[1000, 1004])
def fresh(request):
    world = world_for("wilderness", request.param)
    return world, _points(world)


def _needs():
    return sorted({(r.ground.slope_deg, r.ground.radius + r.ground.margin) for r in RULES.kinds.values()})


def _outer(p) -> float:
    return min(o for s, o in _needs() if p.free[pts.slope_key(s)] >= o)


def _check_p2(world, points):
    t = _terrain(world.terrain, world.spawn[:2], ())
    g = t.ground
    for p in points:
        q = t.quad_at(p.x, p.y)
        assert q is not None and t.base[q], f"{p.id} off Site-eligible ground"
        assert p.z == g.surface_z(p.x, p.y)
        for s, _ in _needs():
            on = Ground(heights=g.heights, origin=g.origin, res=g.res, eligible=t.base & (t.slope <= s))
            r = p.free[pts.slope_key(s)]
            assert on.disc_on_eligible(p.x, p.y, r), f"{p.id}: free {r} at {s} deg is not free"
            if r < pts.FREE_CAP - pts.FREE_STEP:
                # the largest such disc, to within the rounding step
                assert not on.disc_on_eligible(p.x, p.y, r + 2 * pts.FREE_STEP), f"{p.id}: free {r} at {s}"
        assert any(p.free[pts.slope_key(s)] >= o for s, o in _needs()), f"{p.id}: no recipe fits"


def _check_p3(world, points):
    groups = RULES.biomes[world.recipe["biome"]].groups
    lo, hi = groups.within
    assert [p.rank for p in points] == list(range(len(points)))
    assert [p.id for p in points] == [f"site{k}" for k in range(len(points))]
    assert [p.hill for p in points] == sorted(p.hill for p in points), "spares over the hill come last"
    assert [p.group for p in points] == sorted(p.group for p in points)
    by = {}
    for p in points:
        by.setdefault(p.group, []).append(p)
    for g, members in by.items():
        assert len(members) <= max(groups.sizes)
        assert len({m.hill for m in members}) == 1
        for m in members:
            d = [math.hypot(m.x - o.x, m.y - o.y) for o in members if o is not m]
            if d:
                assert lo - 1e-6 <= min(d) <= hi + 0.01, f"{m.id}: nearest Group-mate {min(d):.1f}"
                assert min(d) <= groups.gap
    for a in points:
        for b in points:
            if a.rank >= b.rank:
                continue
            d = math.hypot(a.x - b.x, a.y - b.y)
            assert d >= _outer(a) + _outer(b) + CLEAR_WIDTH - 1e-6, f"{a.id}, {b.id} too close"
            if a.group != b.group and not (a.hill and b.hill):
                assert d >= groups.spacing - 1e-6, f"{a.id}, {b.id}: Groups {d:.0f} u apart"


def _check_count(world, points):
    t = _terrain(world.terrain, world.spawn[:2], ())
    want = pts.offer_count(RULES, world.recipe["biome"], float(t.reached.sum()) * t.ground.res ** 2)
    assert len(points) == want


def test_p2_points_stand_on_eligible_ground_with_true_free_radii(case):
    _check_p2(*case)


def test_p3_points_come_in_groups_within_gap_and_spacing(case):
    _check_p3(*case)


def test_enough_points_for_dense_twice_over(case):
    _check_count(*case)


def test_fresh_landscapes_hold_p2_p3_and_the_count(fresh):
    _check_p2(*fresh)
    _check_p3(*fresh)
    _check_count(*fresh)


def test_the_corpus_has_groups_and_spares_over_the_hill():
    sized = {}
    for name in LANDSCAPES:
        world = load(WORLDS / f"{name}.json")
        points = _points(world)
        if name.startswith("outdoor"):
            assert any(p.hill for p in points), name
            poly = _hill(world)
            assert all(p.hill == pts._inside(poly, p.x, p.y) for p in points)
        else:
            assert not any(p.hill for p in points)
        for p in points:
            sized[p.group, name] = sized.get((p.group, name), 0) + 1
    assert max(sized.values()) >= 2


def test_same_inputs_same_text_and_the_seed_moves_them(case):
    world, points = case
    assert _text(_points(world)) == _text(points)
    other = pts.site_points(world.terrain, world.spawn, world.recipe["seed"] + 1, world.recipe["biome"],
                            RULES, hill=_hill(world))
    assert _text(other) != _text(points)


def test_no_sites_control_or_inhabitant_is_read(monkeypatch):
    world = load(WORLDS / "wilderness_plains.json")
    want = _text(_points(world))

    def boom(*a, **k):
        raise AssertionError("site_points read a Sites control or Inhabitant")
    for name in ("density", "draw_inhabitant", "draw_kind", "kind_chances", "kind_weights",
                 "inhabitant_chances", "recipe_for"):
        monkeypatch.setattr(SiteRules, name, boom)
    assert _text(_points(world)) == want


def test_a_biome_without_groups_is_refused():
    from dataclasses import replace
    rules = replace(RULES, biomes={"plains": replace(RULES.biomes["plains"], groups=None)})
    world = load(WORLDS / "wilderness_plains.json")
    with pytest.raises(ValueError, match="groups"):
        _points(world, rules)
