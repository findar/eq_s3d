"""Trees in the wilderness build (trees spec task 5).

Properties T5-T9 on real builds: the TER is identical at every Density_Level
(Req 7.1); trunks never cut anything off from Spawn (Req 6); the archive and
ZON agree (Req 8.1-8.2); ``none`` and room-graph builds carry no models or
objects (Req 4.4, 10.1); the same inputs give the same ``.eqg`` (Req 11.1).

The PFS footer holds the write time (``core/pfs.py``), so "byte-identical"
compares everything but the archive's last 4 bytes.
"""

import json
import math

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.ter import TerFile
from core.zon import ZonFile
from generators.builder import ZoneBuilder
from generators.pipeline import generate_validated
from generators.vegetation.kit import load_vegetation_kit
from generators.vegetation.placement import TreeInstance
from generators.wilderness import build as wbuild
from generators.wilderness.build import (
    bowl_report,
    build_wilderness_ter,
    trees_block,
    vegetation_for,
    wilderness_spec,
)

EDGES = {"N": "zoneline", "E": "river"}
LEVELS = ("none", "sparse", "normal", "dense")


def _spec(seed, level=None, edges=EDGES, name="karana"):
    spec = plan_to_spec(ZonePlan(name=name, zone_type="wilderness"), seed=seed, edges=edges)
    spec.sites = "none"  # step 2's tree properties are about tree-only zones
    if level is not None:
        spec.wilderness["trees"] = level
    return spec


def _build(tmp_path, spec, sub):
    return ZoneBuilder(spec).build(output_dir=tmp_path / sub, write_glb=False)


def _archive(result):
    arc = PfsArchive.from_file(result.eqg_path)
    return arc, ZonFile.from_bytes(arc.get(f"{result.spec.name}.zon"))


def test_property_t5_ter_is_identical_at_every_level(tmp_path):
    ters = []
    for level in LEVELS:
        r = _build(tmp_path, _spec(31337, level), level)
        arc, _ = _archive(r)
        ters.append(arc.get("ter_karana.ter"))
    assert all(t == ters[0] for t in ters)


@pytest.mark.parametrize("seed, edges", [
    (5, {"N": "zoneline"}), (11, {"E": "river", "S": "zoneline"}),
    (2275961, {"N": "mountain", "E": "mountain", "S": "mountain", "W": "mountain"}),
    (424242, {"W": "zoneline", "E": "zoneline"}),
])
def test_property_t6_trunks_never_cut_anything_off(seed, edges):
    spec = _spec(seed, "dense", edges)
    ter = build_wilderness_ter(spec, "ter_karana", 2)
    veg = vegetation_for(spec, ter)
    assert veg.placement.instances
    assert trees_block(spec, ter, veg.placement.instances) is None
    assert bowl_report(spec, ter).rooms[0].reachable


def test_the_trunk_check_is_not_vacuous(monkeypatch):
    """A wall of touching trunks around Spawn fails the check and the gate."""
    spec = _spec(5, "normal", {"N": "zoneline"})
    ter = build_wilderness_ter(spec, "ter_karana", 2)
    sx, sy, sz = spec.safe_point
    ring = [TreeInstance("broadleaf", sx + 200 * math.cos(a), sy + 200 * math.sin(a),
                         sz, 0.0, 1.0, 3.0)
            for a in (2 * math.pi * k / 240 for k in range(240))]
    assert trees_block(spec, ter, ring) is not None

    real = vegetation_for(spec, ter)
    walled = real.placement.__class__(instances=ring, target=len(ring),
                                      eligible_area=real.placement.eligible_area,
                                      grove_count=0)
    monkeypatch.setattr(wbuild, "vegetation_for",
                        lambda s, t: real.__class__(placement=walled, models={}, textures={},
                                                    model_index={}, report={}))
    room = bowl_report(spec, ter).rooms[0]
    assert not room.reachable and "tree trunks cut off" in room.reason


@pytest.mark.parametrize("seed", [7, 90210])
def test_property_t7_archive_and_zon_agree(tmp_path, seed):
    r = _build(tmp_path, _spec(seed, "normal"), "z")
    arc, zon = _archive(r)
    files = {f.lower() for f in arc.list_files()}
    assert zon.models[0] == "TER_KARANA.TER"
    tree_models = zon.models[1:]
    assert tree_models and len(tree_models) == len(set(tree_models))
    assert {f for f in files if f.endswith(".mod")} == set(tree_models)
    for fname in tree_models:
        model = TerFile.from_bytes(arc.get(fname), name=fname)
        for mat in model.materials:
            for prop in mat.properties:
                if prop.value_s:
                    assert prop.value_s.lower() in files, prop.value_s
    names = [o.name for o in zon.objects]
    assert len(names) == len(set(names)) and zon.objects
    for o in zon.objects:
        assert 1 <= o.model_id < len(zon.models)
        assert -math.pi <= o.yaw < math.pi + 1e-6 and o.pitch == 0.0 and o.roll == 0.0
    side = json.loads(r.sidecar_path.read_text(encoding="utf-8"))["vegetation"]
    assert side["total"] == len(zon.objects) == sum(side["counts"].values())
    assert sorted(side["models"]) == sorted(tree_models)
    assert side["level"] == "normal" and side["level_source"] == "default"


def test_property_t8_none_and_room_graph_builds_have_no_trees(tmp_path):
    cases = [("none", _spec(77, "none"))]
    for zt in ("dungeon", "city"):
        cases.append((zt, plan_to_spec(ZonePlan(name=f"h{zt}", zone_type=zt), seed=77)))
    for sub, spec in cases:
        r = _build(tmp_path, spec, sub)
        arc, zon = _archive(r)
        assert not [f for f in arc.list_files() if f.lower().endswith(".mod")], sub
        assert zon.objects == [] and len(zon.models) == 1, sub
    side = json.loads((tmp_path / "none" / "karana.zone.json").read_text(encoding="utf-8"))
    assert side["vegetation"]["total"] == 0 and side["vegetation"]["models"] == []


def test_property_t9_same_inputs_same_eqg(tmp_path):
    a = _build(tmp_path, _spec(2024, "dense"), "a")
    wbuild._landscape.cache_clear()
    wbuild._vegetation.cache_clear()
    b = _build(tmp_path, _spec(2024, "dense"), "b")
    # Everything but the PFS footer's write time.
    assert a.eqg_path.read_bytes()[:-4] == b.eqg_path.read_bytes()[:-4]


def test_validated_build_carries_trees_through_the_gate(tmp_path):
    vb = generate_validated(
        lambda s: _spec(s, "dense"), zone_type="wilderness", zone_id="karana",
        seed=4040, output_dir=tmp_path, failure_log=None)
    assert vb.validated and vb.attempts == 1
    side = json.loads(vb.result.sidecar_path.read_text(encoding="utf-8"))
    assert side["vegetation"]["total"] > 100
    assert 0.45 <= side["vegetation"]["grove_ratio"] <= 0.85


# ---------------------------------------------------------------------------
# Task 6: the GLB `vegetation` node (Req 9.1)
# ---------------------------------------------------------------------------

def _glb(path):
    import trimesh
    return trimesh.load(path)


def test_glb_has_a_terrain_and_a_vegetation_node(tmp_path):
    spec = _spec(5, "dense", {"N": "zoneline"})
    r = ZoneBuilder(spec).build(output_dir=tmp_path)
    scene = _glb(r.glb_path)
    # The terrain node holds one textured primitive per material (placeholder
    # textures spec Req 6); the trees are the one other mesh.
    nodes = scene.graph.nodes_geometry
    assert "vegetation" in nodes
    assert all(n == "vegetation" or n.startswith("terrain_") for n in nodes)
    assert "terrain" in scene.graph.nodes

    veg = vegetation_for(spec, build_wilderness_ter(spec, "ter_karana", 2))
    per_model = {fname: len(m.vertices) for fname, m in veg.models.items()}
    want = sum(per_model[veg.model_index[t.species]] for t in veg.placement.instances)
    mesh = scene.geometry["vegetation"]
    assert len(mesh.vertices) == want

    # Every tree stands where the ZON places it: its trunk base (the lowest
    # vertices) sits under the tree's XY, below its Z.
    import numpy as np
    for t in veg.placement.instances[:20]:
        near = np.hypot(mesh.vertices[:, 0] - t.x, mesh.vertices[:, 1] - t.y) < t.radius + 0.01
        assert near.any() and mesh.vertices[near, 2].min() < t.z
    colors = {tuple(c[:3]) for c in mesh.visual.vertex_colors}
    kit_colors = {c for sp in load_vegetation_kit("plains_grassland").species.values()
                  for c in (sp.bark, sp.leaf)}
    assert colors <= kit_colors and len(colors) >= 2


@pytest.mark.parametrize("zone_type", ["dungeon", "none-wilderness"])
def test_glb_without_trees_is_the_single_terrain_mesh(tmp_path, zone_type):
    if zone_type == "dungeon":
        spec = plan_to_spec(ZonePlan(name="hdungeon", zone_type="dungeon"), seed=1)
    else:
        spec = _spec(5, "none", {"N": "zoneline"})
    r = ZoneBuilder(spec).build(output_dir=tmp_path)
    scene = _glb(r.glb_path)
    nodes = scene.graph.nodes_geometry
    assert "vegetation" not in nodes
    assert nodes and all(n.startswith("terrain_") for n in nodes)


# ---------------------------------------------------------------------------
# Task 12: vegetation adds at most 3 s to a dense build (Req 11.2)
# ---------------------------------------------------------------------------

VEGETATION_BUDGET_S = 3.0


def _timed_build_and_gate(tmp_path, spec, sub):
    """Seconds for one build (EQG + GLB) plus the bowl gate the pipeline runs."""
    import time

    from generators.pipeline import load_ter_from_eqg

    wbuild._vegetation.cache_clear()
    t0 = time.perf_counter()
    result = ZoneBuilder(spec).build(output_dir=tmp_path / sub)
    ter, _ = load_ter_from_eqg(result.eqg_path)
    report = bowl_report(spec, ter)
    elapsed = time.perf_counter() - t0
    assert report.passed, report.notes
    return elapsed


@pytest.mark.slow
def test_dense_trees_add_at_most_3s(tmp_path):
    seed = 1955208177
    # Warm the landscape cache both builds share, so the difference is only
    # what vegetation costs: models, textures, placement, GLB node and the
    # trunk walkability check. Best of two each, against scheduler noise.
    _timed_build_and_gate(tmp_path, _spec(seed, "none"), "warm")
    none = min(_timed_build_and_gate(tmp_path, _spec(seed, "none"), f"n{i}") for i in range(2))
    dense = min(_timed_build_and_gate(tmp_path, _spec(seed, "dense"), f"d{i}") for i in range(2))
    assert dense - none <= VEGETATION_BUDGET_S, (
        f"dense build {dense:.2f}s vs none {none:.2f}s: vegetation adds "
        f"{dense - none:.2f}s (budget {VEGETATION_BUDGET_S:g}s)")
