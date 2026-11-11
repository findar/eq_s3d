"""
tests/test_decor_builds.py
--------------------------
Decor in builds (room-decor spec task 9; Reqs 6.4, 9, 10.3, 10.5, 10.6, 12.2, 12.3).

- Decor ``none`` (and Decor wanted with no install) builds step 10's bytes: the
  ``tests/test_layout_engine.py`` goldens, for every zone type (P6, Req 10.6).
- With the install (``EQ_PATH``; these skip without it, as the survey tests do):
  dungeon, city and outdoor-dungeon builds place Props, pack each model in use
  once with one ZON object per Prop, keep the TER unchanged, write the sidecar's
  ``props``/``dressing``/``decor_drops`` and the GLB ``decor`` mesh, give the same
  ``.eqg`` for the same inputs, and pass the gate, where decor's own room check
  agrees with it (P13).
- P9: one ZON light per light-bearing Prop, and every room's own light stays.

Built ``.eqg`` files here hold the client's art: they live in ``tmp_path`` only.
"""

from __future__ import annotations

import hashlib
import json
import math

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.zon import ZonFile
from generators.builder import NO_INSTALL, ZoneBuilder
from generators.decor.stock import eq_path_from_env
from tests.test_layout_engine import GOLDENS

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

#: Decorated builds: zone type -> (ZonePlan fields, seed). Pinned seeds whose
#: Normal build passes the gate first time (see the commit body for the rate).
DECORATED = {
    "dungeon": (dict(zone_type="dungeon"), 4),
    "city": (dict(zone_type="city"), 5),
    "outdoor_dungeon": (dict(zone_type="outdoor_dungeon", room_count=5), 1),
}


def _spec(fields, seed, decor, name="dec"):
    spec = plan_to_spec(ZonePlan(name=name, **fields).validate(), seed=seed)
    spec.decor = decor
    return spec


def _eqg_hash(path) -> str:
    return hashlib.sha256(path.read_bytes()[:-4]).hexdigest()


def _zon(arc: PfsArchive) -> ZonFile:
    name = next(f for f in arc.list_files() if f.lower().endswith(".zon"))
    return ZonFile.from_bytes(arc.get(name))


# ---------------------------------------------------------------------------
# Decor none: step 10's bytes
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("label", sorted(GOLDENS))
def test_decor_none_is_step_10_bytes(tmp_path, label):
    """Req 6.4 / 12.2 (P6): an explicit Decor ``none`` builds the golden bytes."""
    fields, seed, _spec_golden, eqg_golden = GOLDENS[label]
    spec = plan_to_spec(ZonePlan(name=f"g_{label}", **fields).validate(), seed=seed)
    spec.decor = "none"
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    assert _eqg_hash(result.eqg_path) == eqg_golden
    side = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert "decor" not in side
    assert all("props" not in r for r in side["rooms"])


@pytest.mark.slow
@pytest.mark.parametrize("label", ["dungeon", "city", "outdoor_dungeon"])
def test_no_install_falls_back_to_none_with_a_warning(tmp_path, monkeypatch, label):
    """Req 10.6: Decor wanted, no install: Decor ``none``'s bytes and a warning."""
    monkeypatch.setenv("EQ_PATH", str(tmp_path / "no_install_here"))
    fields, seed, _spec_golden, eqg_golden = GOLDENS[label]
    spec = plan_to_spec(ZonePlan(name=f"g_{label}", **fields).validate(), seed=seed)
    spec.decor = "normal"
    result = ZoneBuilder(spec).build(output_dir=tmp_path / "out", write_glb=False)
    assert _eqg_hash(result.eqg_path) == eqg_golden
    assert NO_INSTALL in result.warnings


def test_decor_rides_in_the_spec_json():
    """The control and the decor seed round-trip, and are left out while unset."""
    from generators.zone_spec import ZoneSpec

    spec = ZoneSpec(name="x")
    assert "decor" not in spec.to_dict() and "decor_seed" not in spec.to_dict()
    spec.decor, spec.decor_seed = "dense", 42
    back = ZoneSpec.from_dict(spec.to_dict())
    assert (back.decor, back.decor_seed) == ("dense", 42)


def test_pipeline_resolves_an_unset_control_to_the_default():
    from generators.decor.rules import DEFAULT_CONTROL
    from generators.pipeline import _with_decor
    from generators.zone_spec import ZoneSpec

    assert _with_decor(ZoneSpec(name="x")).decor == DEFAULT_CONTROL
    assert _with_decor(ZoneSpec(name="x", decor="none")).decor == "none"


# ---------------------------------------------------------------------------
# With the install
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def decorated(tmp_path_factory):
    """Each zone type built with Decor ``none`` and ``normal`` (GLB on)."""
    if EQ is None:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    out = {}
    for label, (fields, seed) in DECORATED.items():
        for decor in ("none", "normal"):
            spec = _spec(fields, seed, decor)
            root = tmp_path_factory.mktemp(f"{label}_{decor}")
            result = ZoneBuilder(spec).build(output_dir=root, write_glb=True)
            out[label, decor] = (spec, result)
    return out


def _loaded(result):
    arc = PfsArchive.from_file(result.eqg_path)
    side = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    return arc, _zon(arc), side


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(DECORATED))
def test_props_are_packed_once_and_placed_one_object_each(decorated, label):
    """Req 10.5: each model in use packed once, one ZON object per Prop; the
    TER is the same whatever the Props (Req 6.4)."""
    _spec_, plain = decorated[label, "none"]
    spec, result = decorated[label, "normal"]
    arc, zon, side = _loaded(result)
    # rooms first, then Sites, as in the ZON (task 20)
    props = ([p for r in side["rooms"] for p in r.get("props", [])]
             + [p for s in side.get("sites", {}).get("sites", []) for p in s.get("props", [])])
    assert props, "no Props placed"
    objs = [o for o in zon.objects if o.name.startswith("decor_")]
    assert len(objs) == len(props) == side["decor"]["props"]
    used = [zon.models[o.model_id] for o in objs]
    assert all(f.startswith("stock_") and f.endswith(".mod") for f in used)
    assert len(zon.models) == len(set(zon.models))
    files = set(arc.list_files())
    assert set(used) <= files
    assert len(set(used)) == side["decor"]["models"]
    for o, p in zip(objs, props):
        assert (o.x, o.y, o.z) == pytest.approx((p["x"], p["y"], p["z"]), abs=1e-3)
        assert o.scale == pytest.approx(p["scale"], abs=1e-3)
    ter = f"ter_{spec.name}.ter"
    assert arc.get(ter) == PfsArchive.from_file(plain.eqg_path).get(ter)
    # Their textures are packed and in the manifest as ``decor``.
    decor_tex = [e for e in side["textures"] if e["texture_mode"] == "decor"]
    assert decor_tex and all(e["texture"] in files for e in decor_tex)


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(DECORATED))
def test_sidecar_lists_props_dressing_and_drops(decorated, label):
    """Req 10.3: per room ``props``, ``dressing`` by POI and ``decor_drops``."""
    spec, result = decorated[label, "normal"]
    _arc, _zon_, side = _loaded(result)
    rooms = {r["id"]: r for r in side["rooms"]}
    assert set(rooms) == {r.id for r in spec.rooms}
    for room in spec.rooms:
        rec = rooms[room.id]
        assert {"props", "dressing", "decor_drops"} <= set(rec)
        for p in rec["props"]:
            assert {"key", "kind", "x", "y", "z", "yaw", "mount"} <= set(p)
        for d in rec["dressing"]:
            assert 0 <= d["poi"] < len(room.pois)
            assert d["purpose"] == room.pois[d["poi"]].purpose
        for d in rec["decor_drops"]:
            assert d["reason"]
    assert result.glb_path is not None and b'"decor"' in result.glb_path.read_bytes()


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(DECORATED))
def test_props_pass_the_gate_and_decor_agrees(decorated, label):
    """The gate on a decorated build (Req 2, 12.2), and decor's own room check
    agrees with it (P13): both find nothing."""
    from generators.pipeline import _traversal_report

    spec, result = decorated[label, "normal"]
    _arc, _zon_, side = _loaded(result)
    report = _traversal_report(result.eqg_path, spec, None)
    failures = [o.reason for o in report.outlines if not o.ok]
    assert report.passed and report.corridors_passed and not failures, failures
    assert side["decor"]["check"] == []


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label, seed", [("dungeon", 101), ("dungeon", 105), ("outdoor_dungeon", 119),
                                         ("outdoor_dungeon", 4)])
def test_decor_agrees_with_the_gate_where_it_once_didnt(tmp_path, label, seed):
    """P13: seeds where placement once kept Props the gate failed (a chest shutting a
    treasure POI in a corner, floor by a wall read as walkable, a 2.97 u chest on floor
    sloping away read as one step) now pass both."""
    from generators.pipeline import _traversal_report

    fields = dict(zone_type=label, **({"room_count": 5} if label == "outdoor_dungeon" else {}))
    spec = _spec(fields, seed, "normal")
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    side = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert side["decor"]["props"] > 0 and side["decor"]["check"] == []
    report = _traversal_report(result.eqg_path, spec, None)
    failures = [o.reason for o in report.outlines if not o.ok]
    assert report.passed and not failures, failures


@pytest.mark.slow
@needs_install
def test_same_inputs_same_eqg(tmp_path):
    """Req 12.3: the same inputs and install give the same ``.eqg`` (footer aside)."""
    fields, seed = DECORATED["dungeon"]
    a = ZoneBuilder(_spec(fields, seed, "normal")).build(output_dir=tmp_path / "a", write_glb=False)
    b = ZoneBuilder(_spec(fields, seed, "normal")).build(output_dir=tmp_path / "b", write_glb=False)
    assert _eqg_hash(a.eqg_path) == _eqg_hash(b.eqg_path)


@pytest.mark.slow
@needs_install
def test_decor_seed_changes_only_props(tmp_path):
    """A decor seed rerolls Props and leaves the TER alone (Req 10.2, P10)."""
    fields, seed = DECORATED["dungeon"]
    spec_a = _spec(fields, seed, "normal")
    spec_b = _spec(fields, seed, "normal")
    spec_b.decor_seed = seed + 1
    a = ZoneBuilder(spec_a).build(output_dir=tmp_path / "a", write_glb=False)
    b = ZoneBuilder(spec_b).build(output_dir=tmp_path / "b", write_glb=False)
    arc_a, arc_b = PfsArchive.from_file(a.eqg_path), PfsArchive.from_file(b.eqg_path)
    ter = f"ter_{spec_a.name}.ter"
    assert arc_a.get(ter) == arc_b.get(ter)
    side_a = json.loads(a.sidecar_path.read_text(encoding="utf-8"))
    side_b = json.loads(b.sidecar_path.read_text(encoding="utf-8"))
    assert [r.get("props") for r in side_a["rooms"]] != [r.get("props") for r in side_b["rooms"]]


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(DECORATED))
def test_light_one_zon_light_per_light_bearing_prop(decorated, label):
    """P9 (Req 9.1): one ZON point light per light-bearing Prop, near it, and
    every room's own light stays."""
    spec, result = decorated[label, "normal"]
    _arc, zon, side = _loaded(result)
    props = [p for r in side["rooms"] for p in r.get("props", [])]
    lit = [p for p in props if p["category"] == "light"]
    assert lit, "no light-bearing Prop placed"
    names = [l.name for l in zon.lights]
    assert [n for n in names if not n.startswith("decor_light_")] == [l.id for l in spec.lights]
    extra = [l for l in zon.lights if l.name.startswith("decor_light_")]
    assert len(extra) == len(lit) == side["decor"]["lights"]
    for light, p in zip(extra, lit):
        # (a model may be drawn wholly over its origin: GENTORCH700 from 12 to 17.4 u up)
        reach = max(p["w"], p["d"], abs(p["h"]), abs(p["below"])) * 1.5 + 1.0
        assert math.dist((light.x, light.y, light.z), (p["x"], p["y"], p["z"])) <= reach


# ---------------------------------------------------------------------------
# Task 13: the first look's findings, on the built zone itself
# ---------------------------------------------------------------------------

def _placed(result):
    """(sidecar row, world vertices (V, 3), the terrain's triangles (T, 3, 3) and their
    declared normals (T, 3)) for every Prop of a built zone, read from the ``.eqg``."""
    import numpy as np
    from core.ter import TerFile

    arc, zon, side = _loaded(result)
    ter = TerFile.from_bytes(arc.get(next(f for f in arc.list_files() if f.startswith("ter_"))))
    v = np.array([(p.x, p.y, p.z) for p in ter.vertices])
    vn = np.array([(p.nx, p.ny, p.nz) for p in ter.vertices])
    idx = np.array([(p.v1, p.v2, p.v3) for p in ter.polygons])
    rows = ([p for r in side["rooms"] for p in r.get("props", [])]
            + [p for s in side.get("sites", {}).get("sites", []) for p in s.get("props", [])])
    objs = [o for o in zon.objects if o.name.startswith("decor_")]
    models = {}
    out = []
    for o, p in zip(objs, rows):
        f = zon.models[o.model_id]
        if f not in models:
            m = TerFile.from_bytes(arc.get(f))
            models[f] = np.array([(q.x, q.y, q.z) for q in m.vertices])
        c, s = math.cos(o.yaw), math.sin(o.yaw)
        rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        out.append((p, models[f] @ rot.T * o.scale + (o.x, o.y, o.z)))
    return out, v[idx], vn[idx].mean(axis=1)


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(DECORATED))
def test_floor_props_stand_on_the_floor_under_them(decorated, label):
    """Task 13 finding 3 (a box below the world): every floor and raised Prop's model, as
    the ``.eqg`` places it, has its bottom no lower than the lowest floor of the built mesh
    under its plan and its top over the highest."""
    import numpy as np
    from generators.room_context import _sample

    _spec_, result = decorated[label, "normal"]
    props, tri, normal = _placed(result)
    up = tri[normal[:, 2] > 0.5]
    n = 0
    for p, w in props:
        if p["mount"] not in ("floor", "raised"):
            continue
        lo, hi = w.min(axis=0), w.max(axis=0)
        near = up[(up[:, :, 2].max(axis=1) <= hi[2]) & (up[:, :, 2].min(axis=1) >= lo[2] - 20.0)]
        xs, ys = np.arange(lo[0], hi[0] + 0.01, 0.5), np.arange(lo[1], hi[1] + 0.01, 0.5)
        floor = _sample(near, xs, ys, "max")
        # the points under its plan (the model's own extent, turned with it)
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        c, s = math.cos(p["yaw"]), math.sin(p["yaw"])
        mid = (lo + hi) / 2
        lx = c * (gx - mid[0]) + s * (gy - mid[1])
        ly = -s * (gx - mid[0]) + c * (gy - mid[1])
        inside = (np.abs(lx) <= p["w"] / 2) & (np.abs(ly) <= p["d"] / 2) & ~np.isnan(floor)
        if not inside.any():
            continue
        n += 1
        under = floor[inside]
        assert lo[2] >= under.min() - 0.01, (p["key"], lo[2], under.min())
        assert hi[2] > under.max(), (p["key"], hi[2], under.max())
    assert n > 3


@pytest.mark.slow
@needs_install
def test_light_none_adds_no_lights(decorated):
    """With Decor ``none`` the ZON lights are the rooms' own."""
    spec, result = decorated["dungeon", "none"]
    _arc, zon, _side = _loaded(result)
    assert [l.name for l in zon.lights] == [l.id for l in spec.lights]
