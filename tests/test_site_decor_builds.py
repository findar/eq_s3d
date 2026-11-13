"""Room-decor task 20: Site Props in built zones (Reqs 10.1, 11).

- Decor ``none`` builds step 10's bytes for the wilderness and the outdoor dungeon (the
  ``tests/test_layout_engine.py`` goldens), and so does Sites ``none`` with Decor wanted: a
  wilderness with no Sites has nothing to dress.
- With the install (``EQ_PATH``; these skip without it): a built wilderness carries its Sites'
  Props as ZON objects (each model packed once), a ZON light per light-bearing Prop, and per
  Site ``props``/``dressing``/``decor_drops`` rows on the sidecar's ``sites`` block; the TER is
  the same whatever the Props; the gate takes the build. An outdoor dungeon carries both its
  rooms' Props and its Sites'.
- Only models the open-ground screen took (the catalogue's ``open_ground``) stand at a Site.

The 40-seed gate run (P11) is ``tests/test_site_props.py``. Built ``.eqg`` files here hold
the client's art: they live in ``tmp_path`` only.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.zon import ZonFile
from generators.builder import ZoneBuilder
from generators.decor.stock import eq_path_from_env
from tests.test_layout_engine import GOLDENS

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

#: Pinned builds: label -> (ZonePlan fields, seed).
BUILDS = {
    "wilderness": (dict(zone_type="wilderness"), 4),
    "outdoor_dungeon": (dict(zone_type="outdoor_dungeon", room_count=5), 1),
}


def _spec(fields, seed, decor, name="sd", sites=None):
    spec = plan_to_spec(ZonePlan(name=name, **fields).validate(), seed=seed)
    spec.decor = decor
    if sites is not None:
        spec.sites = sites
    return spec


def _eqg_hash(path) -> str:
    return hashlib.sha256(path.read_bytes()[:-4]).hexdigest()


def _loaded(result):
    arc = PfsArchive.from_file(result.eqg_path)
    zon = ZonFile.from_bytes(arc.get(next(f for f in arc.list_files() if f.lower().endswith(".zon"))))
    side = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    return arc, zon, side


def _site_props(side) -> list:
    return [p for s in side.get("sites", {}).get("sites", []) for p in s.get("props", [])]


def _room_props(side) -> list:
    return [p for r in side["rooms"] for p in r.get("props", [])]


# ---------------------------------------------------------------------------
# Decor none, Sites none: step 10's bytes
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("label", ["wilderness", "outdoor_dungeon"])
def test_decor_none_is_step_10_bytes(tmp_path, label):
    fields, seed, _spec_golden, eqg_golden = GOLDENS[label]
    spec = plan_to_spec(ZonePlan(name=f"g_{label}", **fields).validate(), seed=seed)
    spec.decor = "none"
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    assert _eqg_hash(result.eqg_path) == eqg_golden
    side = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert "decor" not in side and not _site_props(side)


@pytest.mark.slow
def test_sites_none_with_decor_is_decor_none(tmp_path):
    """A wilderness with no Sites has nothing to dress: Decor ``dense`` builds the bytes and
    the sidecar of Decor ``none``."""
    fields, seed = BUILDS["wilderness"]
    a = ZoneBuilder(_spec(fields, seed, "none", sites="none")).build(output_dir=tmp_path / "a",
                                                                      write_glb=False)
    b = ZoneBuilder(_spec(fields, seed, "dense", sites="none")).build(output_dir=tmp_path / "b",
                                                                       write_glb=False)
    assert _eqg_hash(a.eqg_path) == _eqg_hash(b.eqg_path)
    assert a.sidecar_path.read_bytes() == b.sidecar_path.read_bytes()


# ---------------------------------------------------------------------------
# With the install
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Each pinned build with Decor ``none`` and ``dense`` (GLB on)."""
    if EQ is None:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    out = {}
    for label, (fields, seed) in BUILDS.items():
        for decor in ("none", "dense"):
            spec = _spec(fields, seed, decor)
            root = tmp_path_factory.mktemp(f"{label}_{decor}")
            out[label, decor] = (spec, ZoneBuilder(spec).build(output_dir=root, write_glb=True))
    return out


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(BUILDS))
def test_site_props_are_zon_objects_lights_and_sidecar_rows(built, label):
    _spec_, plain = built[label, "none"]
    spec, result = built[label, "dense"]
    arc, zon, side = _loaded(result)
    sites = side["sites"]["sites"]
    props = _site_props(side)
    assert props, "no Site Props placed"
    # The ZON: the rooms' Props, the corridors', then the Sites', one object each;
    # each model packed once.
    objs = [o for o in zon.objects if o.name.startswith("decor_")]
    corridors = [p for r in side.get("corridors", []) for p in r.get("props", [])]
    rows = _room_props(side) + corridors + props
    assert len(objs) == len(rows) == side["decor"]["props"]
    for o, p in zip(objs, rows):
        assert (o.x, o.y, o.z) == pytest.approx((p["x"], p["y"], p["z"]), abs=1e-3)
    used = {zon.models[o.model_id] for o in objs}
    assert len(zon.models) == len(set(zon.models)) and used <= set(arc.list_files())
    assert len(used) == side["decor"]["models"]
    # A ZON light per light-bearing Prop, after the zone's own.
    lit = [p for p in rows if p["category"] == "light"]
    assert len([l for l in zon.lights if l.name.startswith("decor_light_")]) == len(lit)
    # Per Site: props, dressing by POI, drops; the summary counts the Sites.
    assert side["decor"]["sites"] == len(sites) and side["decor"]["check"] == []
    assert side["decor"]["rooms"] == len(spec.rooms)
    for n, s in enumerate(sites):
        assert {"props", "dressing", "decor_drops", "bare"} <= set(s)
        for d in s["dressing"]:
            assert d["purpose"] == s["pois"][d["poi"]]["purpose"]
    # Site rows stay off the rooms' list.
    assert {r["id"] for r in side["rooms"]} == {r.id for r in spec.rooms}
    # The same TER whatever the Props (Req 6.4).
    ter = f"ter_{spec.name}.ter"
    assert arc.get(ter) == PfsArchive.from_file(plain.eqg_path).get(ter)
    assert result.glb_path is not None and b'"decor"' in result.glb_path.read_bytes()


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(BUILDS))
def test_a_built_zone_with_site_props_passes_the_gate(built, label):
    from generators.pipeline import _traversal_report

    spec, result = built[label, "dense"]
    report = _traversal_report(result.eqg_path, spec, None)
    failures = [o.reason for o in report.outlines if not o.ok]
    assert report.passed and not failures, ([r.reason for r in report.rooms if not r.reachable], failures)


@pytest.mark.slow
@needs_install
def test_only_screened_models_stand_at_a_site(built):
    from generators.decor.catalogue import load

    models = load().models
    for label in BUILDS:
        _spec_, result = built[label, "dense"]
        _arc, _zon, side = _loaded(result)
        assert all(models[p["key"]].open_ground is True for p in _site_props(side))


def test_the_screen_is_in_the_catalogue():
    """Every floor and raised model (skeletal aside) carries the measured flag; no other."""
    from generators.decor.catalogue import load

    models = load().models.values()
    for m in models:
        screened = m.animation != "skeletal" and m.tags.mount in ("floor", "raised")
        assert (m.open_ground is not None) == screened, m.key
    assert any(m.open_ground for m in models) and any(m.open_ground is False for m in models)


def test_decor_applies_to_the_wilderness():
    from ai.schema import DECOR_ZONE_TYPES, SITES_ZONE_TYPES

    assert set(SITES_ZONE_TYPES) <= set(DECOR_ZONE_TYPES)
    plan = ZonePlan.from_controls({"zone_type": "wilderness", "decor": "dense", "decor_seed": 3})
    spec = plan_to_spec(plan, seed=4)
    assert (spec.decor, spec.decor_seed) == ("dense", 3)
