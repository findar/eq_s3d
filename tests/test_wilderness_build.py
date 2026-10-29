"""Wilderness end-to-end build (wilderness spec task 2).

The wilderness pipeline (matrix -> rewrite -> synth -> bowl) wired into the
real build: the dev flag, the CLI edge declaration, the backend hook, the bowl
gate in ``generate_validated`` and the per-region preview materials. The
plain-terrain path staying byte-identical is pinned separately by
``test_hygiene.py::test_outdoor_ter_matches_fork_point``.
"""

from __future__ import annotations

import time

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.traverse import load_ter_from_eqg
from generators.pipeline import DEFAULT_TIMEOUT_S, generate_validated
from generators.wilderness.build import (
    _landscape,
    bowl_report,
    build_wilderness_ter,
    normalise_edges,
    parse_edges,
    wilderness_spec,
)
from generators.zone_types import (
    DEV_WILDERNESS_ENV,
    is_enabled,
    zone_type_listing,
)


@pytest.fixture
def dev_wilderness(monkeypatch):
    monkeypatch.setenv(DEV_WILDERNESS_ENV, "1")


def test_wilderness_disabled_without_the_dev_flag(monkeypatch):
    monkeypatch.delenv(DEV_WILDERNESS_ENV, raising=False)
    assert not is_enabled("wilderness")
    wild = next(z for z in zone_type_listing() if z["name"] == "wilderness")
    assert wild["enabled"] is False and wild["reason"]


def test_dev_flag_offers_wilderness(dev_wilderness):
    assert is_enabled("wilderness")
    wild = next(z for z in zone_type_listing() if z["name"] == "wilderness")
    assert wild == {"name": "wilderness", "enabled": True, "reason": None}


def test_edge_declarations_parse_and_default_to_mountain():
    assert parse_edges("n=zoneline, E=river") == {
        "N": "zoneline", "E": "river", "S": "mountain", "W": "mountain"}
    assert normalise_edges(None) == dict.fromkeys("NESW", "mountain")
    with pytest.raises(ValueError, match="side"):
        parse_edges("Q=river")
    with pytest.raises(ValueError, match="type"):
        parse_edges("N=lake")


def test_wilderness_plan_builds_an_open_landscape_spec():
    plan = ZonePlan(name="karana", zone_type="wilderness")
    spec = plan_to_spec(plan, seed=1337, edges={"N": "zoneline"})
    assert spec.zone_type == "wilderness"
    assert spec.rooms == [] and spec.corridors == []
    assert spec.wilderness == {
        "biome": "plains",
        "edges": {"N": "zoneline", "E": "mountain", "S": "mountain", "W": "mountain"},
    }
    assert any(r.kind == "zoneline" for r in spec.regions)
    # Round-trips through JSON, payload included.
    assert type(spec).from_dict(spec.to_dict()).wilderness == spec.wilderness


def test_room_graph_specs_do_not_serialize_a_wilderness_key():
    spec = plan_to_spec(ZonePlan(name="d", zone_type="dungeon"), seed=1)
    assert spec.wilderness is None
    assert "wilderness" not in spec.to_dict()


def test_wilderness_ter_has_a_material_per_region_kind():
    spec = wilderness_spec("k", 2024, {"N": "zoneline", "E": "river"})
    ter = build_wilderness_ter(spec, "ter_k", 2)
    names = {m.name for m in ter.materials}
    assert {"wild_plains", "wild_rim", "wild_zoneline", "wild_water"} <= names
    assert names == set(spec.materials)
    assert {p.material for p in ter.polygons} == set(range(len(ter.materials)))


def test_bowl_gate_rejects_a_flattened_rim():
    """The gate is not vacuous: flatten the mesh and the sealed Rim leaks."""
    spec = wilderness_spec("k", 1337)
    ter = build_wilderness_ter(spec, "ter_k", 2)
    assert bowl_report(spec, ter).passed
    for v in ter.vertices:
        v.z = 0.0
        v.nx, v.ny, v.nz = 0.0, 0.0, 1.0
    report = bowl_report(spec, ter)
    assert not report.passed
    assert report.reachable_rooms == 0 and report.rooms[0].reason


@pytest.mark.slow
def test_generate_validated_gates_wilderness_on_the_bowl(dev_wilderness, tmp_path):
    plan = ZonePlan(name="karana", zone_type="wilderness")
    edges = {"N": "zoneline", "E": "river"}
    vb = generate_validated(
        lambda seed: plan_to_spec(plan, seed=seed, edges=edges),
        zone_type="wilderness", zone_id="karana_t", seed=1337,
        output_dir=tmp_path, failure_log=None,
    )
    assert vb.gated and vb.validated
    assert vb.report is not None and vb.report.rooms[0].room_id == "bowl"
    assert vb.format.passed
    ter, _ = load_ter_from_eqg(vb.result.eqg_path)
    assert len(ter.materials) >= 3
    assert vb.result.glb_path is not None and vb.result.glb_path.exists()


def _generate(tmp_path, zone_id, seed):
    plan = ZonePlan(name="karana", zone_type="wilderness")
    return generate_validated(
        lambda s: plan_to_spec(plan, seed=s, edges={"N": "zoneline", "E": "river"}),
        zone_type="wilderness", zone_id=zone_id, seed=seed,
        output_dir=tmp_path, failure_log=None,
    )


def _ter_bytes(vb) -> bytes:
    ter, _ = load_ter_from_eqg(vb.result.eqg_path)
    return ter.to_bytes()


@pytest.mark.slow
def test_seeded_reproducibility(dev_wilderness, tmp_path):
    """Feature: zone-generator-wilderness, Property 16: Seeded reproducibility.

    The same pinned seed rebuilds the same TER (the landscape cache cleared in
    between, so it really is re-derived); no seed draws a fresh one and the
    landscape differs. The ``.eqg``/``.glb`` need not be byte-identical.
    """
    first = _generate(tmp_path, "karana_a", 2024)
    _landscape.cache_clear()
    again = _generate(tmp_path, "karana_b", 2024)
    assert first.seed == again.seed == 2024
    assert _ter_bytes(first) == _ter_bytes(again)

    fresh = [_generate(tmp_path, f"karana_r{i}", None) for i in range(2)]
    assert fresh[0].seed != fresh[1].seed
    assert _ter_bytes(fresh[0]) != _ter_bytes(fresh[1])


@pytest.mark.slow
def test_full_generate_fits_the_time_budget(dev_wilderness, tmp_path):
    """A full gated wilderness generate (build, bowl gate, format check, GLB)
    is far under the 5-minute budget and inside the pipeline's own timeout."""
    _landscape.cache_clear()  # time a cold build, not a cache hit
    t0 = time.perf_counter()
    vb = _generate(tmp_path, "karana_t", 1337)
    elapsed = time.perf_counter() - t0
    assert vb.validated
    assert elapsed < DEFAULT_TIMEOUT_S["wilderness"] < 300.0, elapsed
