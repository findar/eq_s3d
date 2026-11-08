"""Wilderness POIs task 7: Sites in builds (Req 4.4, 7, 8.2, 8.4, 9.2, 9.3).

Builds place Sites and pass the gate with them; Sites ``none`` is step 9's
bytes; the same inputs give the same ``.eqg``; outdoor dungeons keep step 5's
guarantees and their Apron, Tunnel, Mouth and Host_Hill clear (P8)."""

import hashlib
import json
from functools import lru_cache

import pytest

from core.pfs import PfsArchive
from core.zon import ZonFile
from generators import outdoor_dungeon as od
from generators.builder import ZoneBuilder
from generators.pipeline import load_ter_from_eqg
from generators.sites.placement import gap
import generators.wilderness.build as wb

# .eqg[:-4] sha256 of master before task 7 (step 9), with the default trees.
# A Sites ``none`` build must still give exactly these (Req 4.4, 9.2).
STEP9 = {
    ("wild", 1955208177): "8aaf8daf8112fbf2d5a6ce2a02c7de3ee60496c33ca82f6d877f8ef66e1f7aa0",
    ("wild", 31337): "413bbd2c9b4268d5c5efe2435ddb8317cb9e78472cf50d5d7f6c52117bba619e",
    ("od", 3): "5c274108bc888fc344488d1ea580ce486cb37e2eed71ce1c13b389c08a84c050",
}


def _spec(kind, seed, sites="normal"):
    spec = (wb.wilderness_spec(f"b{seed}", seed) if kind == "wild"
            else od.outdoor_dungeon_spec(f"b{seed}", seed))
    spec.sites = sites
    return spec


def _build(tmp_path, spec, sub):
    return ZoneBuilder(spec).build(output_dir=tmp_path / sub, write_glb=False)


def _archive(result):
    arc = PfsArchive.from_file(result.eqg_path)
    return arc, ZonFile.from_bytes(arc.get(f"{result.spec.name}.zon"))


@pytest.mark.parametrize("kind, seed", sorted(STEP9))
def test_sites_none_is_step9_bytes(tmp_path, kind, seed):
    r = _build(tmp_path, _spec(kind, seed, "none"), "n")
    assert hashlib.sha256(r.eqg_path.read_bytes()[:-4]).hexdigest() == STEP9[(kind, seed)]
    side = json.loads(r.sidecar_path.read_text(encoding="utf-8"))["sites"]
    assert side["control"] == "none" and side["sites"] == [] and side["models"] == []


@pytest.mark.parametrize("seed, sites", [(1955208177, "normal"), (31337, "dense"), (4, "normal")])
def test_builds_pass_the_gate_with_sites(tmp_path, seed, sites):
    spec = _spec("wild", seed, sites)
    r = _build(tmp_path, spec, "b")
    ter, _ = load_ter_from_eqg(r.eqg_path)
    report = wb.bowl_report(spec, ter)  # what the pipeline runs: Site POIs included
    assert report.passed, report.rooms[0].reason

    placed = wb.sites_for(spec, ter)
    assert placed.placement.sites and placed.pois()
    arc, zon = _archive(r)
    files = {f.lower() for f in arc.list_files()}
    objs = [o for o in zon.objects if o.name.startswith("site_")]
    assert len(objs) == sum(len(s.structures) for s in placed.placement.sites)
    for o in objs:
        fname = zon.models[o.model_id]
        assert fname.startswith("site_") and fname in files
    site_models = {m for m in zon.models if m.startswith("site_")}
    assert {f for f in files if f.startswith("site_") and f.endswith(".mod")} == site_models
    assert {f for f in files if f.startswith("site_") and f.endswith(".dds")}

    side = json.loads(r.sidecar_path.read_text(encoding="utf-8"))["sites"]
    assert side["control"] == sites and sorted(side["models"]) == sorted(site_models)
    for s in side["sites"]:
        assert s["kind"] and s["inhabitant"] and s["structures"] and s["pois"]
    assert "drops" in side


def test_same_inputs_same_eqg(tmp_path):
    a = _build(tmp_path, _spec("wild", 2024, "dense"), "a")
    for f in (wb._landscape, wb._sites, wb._vegetation):
        f.cache_clear()
    b = _build(tmp_path, _spec("wild", 2024, "dense"), "b")
    assert a.eqg_path.read_bytes()[:-4] == b.eqg_path.read_bytes()[:-4]


OD_SEEDS = range(1000, 1012)


@lru_cache(maxsize=1)
def _od_seeds_with_sites():
    """The seeds in OD_SEEDS whose outdoor dungeon gets a Site at dense (placement only, no
    build). Its open ground is small (~0.82e6 u^2), so not every seed draws one."""
    hits = []
    for seed in OD_SEEDS:
        spec = _spec("od", seed, "dense")
        ter = od.build_outdoor_dungeon_ter(spec, "ter_t.ter", 2)
        if wb.sites_for(spec, ter).placement.sites:
            hits.append(seed)
    return tuple(hits)


def test_some_outdoor_dungeons_get_sites():
    """Req 7.1: outdoor dungeons get Sites on their landscape, on some seeds at least."""
    assert len(_od_seeds_with_sites()) >= 2, _od_seeds_with_sites()


@pytest.mark.parametrize("pick", [0, 1])
def test_outdoor_dungeons_keep_step5_with_sites(tmp_path, pick):
    """P8: an outdoor dungeon with Sites (dense: its open ground is small)
    keeps every Site off the Apron, Tunnel, Mouth and Host_Hill, its terrain
    is the Sites-none terrain, and step 5's gate holds: the bowl passes, every
    room is reached from the outdoor Spawn and every corridor is continuous.
    The seeds are the first two in OD_SEEDS that get a Site."""
    seeds = _od_seeds_with_sites()
    if len(seeds) <= pick:
        pytest.fail(f"fewer than {pick + 1} seeds in {OD_SEEDS} get a Site: {seeds}")
    seed = seeds[pick]
    spec = _spec("od", seed, "dense")
    r = _build(tmp_path, spec, "d")
    ter, _ = load_ter_from_eqg(r.eqg_path)
    placed = wb.sites_for(spec, ter).placement
    assert placed.sites, "no Site on this seed: pick another"
    for keep in od.keep_clear_shapes(spec):
        for s in placed.sites:
            for c in s.clear:
                assert gap(c.shape, keep) >= 0.0, (s.kind, c.what, keep)

    report = od.outdoor_dungeon_report(r.eqg_path, spec)
    assert report.rooms[0].room_id == "bowl"
    assert report.passed, report.summary()
    assert report.checked_corridors and report.corridors_passed

    bare = _build(tmp_path, _spec("od", seed, "none"), "n")
    arc, bare_arc = _archive(r)[0], _archive(bare)[0]
    assert arc.get(f"ter_b{seed}.ter") == bare_arc.get(f"ter_b{seed}.ter")
