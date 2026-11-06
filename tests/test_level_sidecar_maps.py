"""
tests/test_level_sidecar_maps.py
--------------------------------
Dungeon verticality task 8 (Requirement 8; design "Controls and sidecar",
finding 4): the sidecar's ``layout`` block records Levels, connectors and
the Stacked_Share, and a stacked build's EQ map files and outline put each
Level on its own depth band.

V9  stacked builds map each Level on its own depth band.

The stacked builds use task 4's vertical test rule set
(``tests/test_topology_levels.py`` ``VERT``) with ``GraphEngine(stacking=True)``,
as task 5's tests do, built through the pipeline (ZoneBuilder plus the map
post-pass that writes the outline and the EQ map files).
"""

from __future__ import annotations

import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import _union_area, layout_sidecar, stacked_share
from generators.eqmap import map_to_world, parse_map_layer
from generators.geometry import AUTO_STAIRS
from generators.layout import LayoutGenerator
from generators.layout_engine import GraphEngine
from generators.pipeline import generate_validated
from generators.topology.ruleset import load_rule_set
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

from tests.test_topology_levels import VERT

# (rooms, seed): two Levels and three Levels on the shipped code.
STACKED = [(8, 1), (12, 4)]


@pytest.fixture(scope="module")
def vert(tmp_path_factory):
    p = tmp_path_factory.mktemp("rules") / "vert.toml"
    p.write_text(VERT, encoding="utf-8")
    return load_rule_set(p)


@pytest.fixture(scope="module", params=STACKED, ids=lambda p: f"n{p[0]}s{p[1]}")
def stacked_build(request, vert, tmp_path_factory):
    n, seed = request.param
    name = f"lvmap{n}_{seed}"

    def factory(s):
        gen = LayoutGenerator("dungeon", seed=s, engine=GraphEngine(vert, stacking=True))
        spec = gen.generate(name, room_count=n)
        spec.layout = gen.layout_record          # as ai.expand.plan_to_spec does
        return spec

    vb = generate_validated(factory, zone_type="dungeon", zone_id=name, seed=seed,
                            output_dir=tmp_path_factory.mktemp(name),
                            write_glb=False, failure_log=None)
    side = json.loads((vb.build_dir / f"{name}.zone.json").read_text(encoding="utf-8"))
    return vb, side


# ---------------------------------------------------------------------------
# The sidecar's layout block
# ---------------------------------------------------------------------------

def test_stacked_sidecar_records_levels_connectors_and_share(stacked_build):
    vb, side = stacked_build
    spec, lay = vb.spec, side["layout"]
    assert lay["levels"] == spec.layout["levels"]
    assert len(set(lay["levels"].values())) > 1
    assert set(lay["connectors"]) == {c.id for c in spec.corridors}
    levels = lay["levels"]
    for c in spec.corridors:
        rec = lay["connectors"][c.id]
        extra = {"over"} if c.bridge else set()
        assert set(rec) == {"kind", "rise", "risers", "switchback"} | extra
        assert rec["rise"] == pytest.approx(abs(c.to_z - c.from_z), abs=0.01)
        if levels[c.from_room] != levels[c.to_room]:
            # Every edge across Levels is a planned stair (task 5).
            assert c.steps == AUTO_STAIRS and rec["kind"] == "stair"
            assert rec["risers"] >= rec["rise"] / 2.0 - 1e-6     # Riser_Cap 2 u
        else:
            kinds = ("bridge",) if c.bridge else ("ramp", "flat")
            assert rec["kind"] in kinds and rec["risers"] == 0
            assert rec["switchback"] is False
    assert any(r["switchback"] for r in lay["connectors"].values())
    assert 0.0 < lay["stacked_share"] < 1.0
    assert lay["stacked_share"] == stacked_share(spec)


def test_unstacked_graph_and_classic_blocks():
    """A graph build on one Level gets the keys (all Level 0, share 0); a
    classic build leaves them out (its block is step 6's)."""
    graph = plan_to_spec(ZonePlan(name="g1", room_count=6, layout="graph",
                                  verticality="flat").validate(),
                         seed=3)
    lay = layout_sidecar(graph)
    assert set(lay["levels"].values()) == {0}
    assert lay["stacked_share"] == 0.0
    assert all(r["kind"] != "stair" for r in lay["connectors"].values())
    classic = plan_to_spec(ZonePlan(name="c1", room_count=6, layout="classic").validate(),
                           seed=3)
    assert not {"levels", "connectors", "stacked_share"} & set(layout_sidecar(classic))


def test_stacked_share_method():
    """Floor area under a room on a higher Level, over all room floor area."""
    spec = ZoneSpec(name="share", zone_type="dungeon")
    spec.rooms = [RoomSpec("low", 0, 0, floor_z=0, width=100, depth=100),
                  RoomSpec("high", 50, 0, floor_z=150, width=100, depth=100),
                  RoomSpec("top", 0, 0, floor_z=300, width=100, depth=100)]
    spec.layout = {"engine": "graph", "levels": {"low": 0, "high": 1, "top": 2}}
    # low: covered by the union of high and top = 100 x 100 (all of it);
    # high: half under top; top: nothing above.
    assert stacked_share(spec) == pytest.approx((10000 + 5000) / 30000, abs=1e-4)
    assert _union_area([(0, 0, 10, 10), (5, 5, 15, 15)]) == pytest.approx(175)
    spec.corridors = [CorridorSpec("c", 0, 0, 1, 0, from_z=0, to_z=150,
                                   steps=10, from_room="low", to_room="high")]
    rec = layout_sidecar(spec)["connectors"]["c"]
    assert rec == {"kind": "stair", "rise": 150.0, "risers": 10, "switchback": False}


def test_outdoor_dungeon_accepts_verticality():
    """The Controls panel now sends verticality for an outdoor dungeon; the
    plan keeps it and expands without error (task 7 makes it act)."""
    for v in ("flat", "moderate", "dramatic"):
        warnings: list = []
        plan = ZonePlan.from_controls({"zone_type": "outdoor_dungeon", "rooms": 5,
                                       "verticality": v, "layout": "graph"}, warnings)
        assert plan.verticality == v
        assert not [w for w in warnings if "verticality" in str(w)]
        plan.name = f"odv_{v}"
        spec = plan_to_spec(plan, seed=5)
        assert spec.rooms and "levels" in layout_sidecar(spec)


# ---------------------------------------------------------------------------
# V9: each Level on its own depth band
# ---------------------------------------------------------------------------

def _band_of(bands, z):
    (band,) = [b for b in bands
               if (b["z_lo"] is None or z >= b["z_lo"]) and (b["z_hi"] is None or z < b["z_hi"])]
    return band["index"]


def test_v9_each_level_on_its_own_band_and_map_layer(stacked_build):
    vb, side = stacked_build
    spec, levels = vb.spec, side["layout"]["levels"]
    bands = side["outline"]["bands"]
    # One EQ map layer (file) per stacked Level.
    assert len(bands) == len(set(levels.values()))
    assert all(b["file"] for b in bands)
    assert {b["file"] for b in bands} <= set(side["map_files"])

    # Each Level's room floors lie on one band, and different Levels on
    # different bands.
    band_of_level = {}
    for r in spec.rooms:
        band_of_level.setdefault(levels[r.id], set()).add(_band_of(bands, r.floor_z))
    assert all(len(b) == 1 for b in band_of_level.values()), band_of_level
    assert len({next(iter(b)) for b in band_of_level.values()}) == len(band_of_level)

    # Each room's walls are drawn in its band's map file.
    layers = {}
    for b in bands:
        parsed = parse_map_layer((vb.build_dir / b["file"]).read_text(encoding="utf-8"),
                                 b["index"])
        assert not parsed.skipped, parsed.skipped
        layers[b["index"]] = parsed.layer
    for r in spec.rooms:
        x0, x1 = r.center_x - r.width / 2 - 1, r.center_x + r.width / 2 + 1
        y0, y1 = r.center_y - r.depth / 2 - 1, r.center_y + r.depth / 2 + 1

        def in_room(mx, my, mz):
            x, y, z = map_to_world(mx, my, mz)
            return x0 <= x <= x1 and y0 <= y <= y1 and abs(z - r.floor_z) < 4.0

        layer = layers[_band_of(bands, r.floor_z)]
        assert any(in_room(l.x1, l.y1, l.z1) and in_room(l.x2, l.y2, l.z2)
                   for l in layer.lines), r.id
