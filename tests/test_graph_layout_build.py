"""Graph-layout task 12 (Req 8.2, 8.3; design G12): the gate sweep on built
zones.

Graph-layout zones are built through the real pipeline (build, walkability
gate, format check, retry on a fresh seed) over a fixed seed list:

- dungeon x each base set (``classic_eq``, ``warren``) x plain, ``temple``
  and ``fortress`` (a theme that maps kinds to its own room types);
- outdoor dungeon x ``classic_eq`` x ``temple`` and ``fortress``;

each at several room counts. Every build must pass within the pipeline's
retry budget. The same plans are built with the classic layout on the same
attempt seeds (the pipeline draws them from ``random.Random(seed)``), one
attempt each, and graph's first-attempt pass rate must be no worse than
classic's. Both rates are printed (``-s`` shows them).

Also here: the same inputs give the same ``.eqg`` (footer aside,
lessons-learned "Two .eqg writes are never byte-identical"), and the two
outdoor-dungeon bugs the sweep found (a room under the map's edge; the
Spawn left floating over the Apron).

A passing sweep is necessary, not sufficient: nothing here is looked at in
the 3D viewer (task 13 does that).
"""

import random

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.rof2check import check_eqg
from generators import outdoor_dungeon as od
from generators.builder import ZoneBuilder
from generators.pipeline import DEFAULT_MAX_ATTEMPTS, GenerationFailed, generate_validated
from generators.wilderness.build import build_wilderness_ter, landscape_for

#: (zone type, base set, themes, room counts, sweep seeds). Each sweep seed
#: seeds the pipeline's rng, so attempt k draws the same build seed for graph
#: and classic.
SWEEPS = {
    "dungeon-classic_eq": ("dungeon", "classic_eq", ("", "temple", "fortress"),
                           (5, 10, 16), range(6)),
    "dungeon-warren": ("dungeon", "warren", ("", "temple", "fortress"),
                       (5, 10, 16), range(6)),
    "outdoor_dungeon-classic_eq": ("outdoor_dungeon", "classic_eq", ("temple", "fortress"),
                                   (3, 5, 8), range(4)),
}


def _plan(zone_type, layout, rule_set, theme, rooms, name="sweep"):
    return ZonePlan(name=name, zone_type=zone_type, room_count=rooms,
                    dungeon_theme=theme, layout=layout,
                    rule_set=rule_set if layout == "graph" else "").validate()


def _generate(tmp_path, plan, seed, max_attempts):
    """The pipeline's build -> gate -> retry loop; the attempts it took, or
    None when the budget ran out."""
    try:
        vb = generate_validated(lambda s: plan_to_spec(plan, seed=s),
                                zone_type=plan.zone_type, zone_id=plan.name,
                                output_dir=tmp_path, write_glb=False,
                                rng=random.Random(seed), failure_log=None,
                                max_attempts=max_attempts, timeout_s=600.0)
    except GenerationFailed:
        return None
    assert vb.validated
    return vb.attempts


@pytest.mark.slow
@pytest.mark.parametrize("sweep", sorted(SWEEPS))
def test_graph_builds_pass_the_gate_no_worse_than_classic(tmp_path, sweep):
    zone_type, rule_set, themes, counts, seeds = SWEEPS[sweep]
    cases = [(t, n, s) for t in themes for n in counts for s in seeds]
    graph, classic, failed = {}, {}, []
    for k, (theme, rooms, seed) in enumerate(cases):
        g = _generate(tmp_path / f"g{k}", _plan(zone_type, "graph", rule_set, theme, rooms),
                      seed, DEFAULT_MAX_ATTEMPTS)
        c = _generate(tmp_path / f"c{k}", _plan(zone_type, "classic", "", theme, rooms),
                      seed, 1)
        graph[theme, rooms, seed], classic[theme, rooms, seed] = g, c
        if g is None:
            failed.append((theme or "plain", rooms, seed))
    g_first = sum(a == 1 for a in graph.values())
    c_first = sum(a == 1 for a in classic.values())
    retries = sum(a - 1 for a in graph.values() if a)
    print(f"\n{sweep}: graph first-attempt {g_first}/{len(cases)}, "
          f"classic {c_first}/{len(cases)}, graph retries {retries}")
    for theme in themes:
        gt = sum(a == 1 for (t, _n, _s), a in graph.items() if t == theme)
        ct = sum(a == 1 for (t, _n, _s), a in classic.items() if t == theme)
        n = sum(1 for (t, _n, _s) in graph if t == theme)
        print(f"  {theme or 'plain'}: graph {gt}/{n}, classic {ct}/{n}")
    assert not failed, f"graph builds out of retries: {failed}"
    assert g_first >= c_first, (sweep, g_first, c_first)


@pytest.mark.slow
@pytest.mark.parametrize("zone_type, rule_set, theme, rooms, seed", [
    ("dungeon", "warren", "temple", 10, 21),
    ("outdoor_dungeon", "classic_eq", "fortress", 5, 4),
])
def test_same_inputs_same_eqg(tmp_path, zone_type, rule_set, theme, rooms, seed):
    """G12 / Req 8.3: a graph build is reproducible (the PFS footer's write
    time aside)."""
    plan = _plan(zone_type, "graph", rule_set, theme, rooms, name="repro")
    eqgs = []
    for k in range(2):
        result = ZoneBuilder(plan_to_spec(plan, seed=seed)).build(
            output_dir=tmp_path / str(k), write_glb=False)
        eqgs.append(result.eqg_path.read_bytes())
    assert eqgs[0][:-4] == eqgs[1][:-4]


def _outdoor(tmp_path, theme, rooms, seed):
    spec = plan_to_spec(_plan("outdoor_dungeon", "graph", "classic_eq", theme, rooms), seed=seed)
    return spec, ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1654615998, 1013818839])
def test_no_room_under_the_map_edge(tmp_path, seed):
    """On these seeds the default hill's disc reaches past the W boundary
    strip, and the graph layout put its climax under it: the bowl gate read
    the room's floor as the flood escaping through the W Rim. The Envelope is
    now the disc clipped to the bowl's interior."""
    spec, result = _outdoor(tmp_path, "temple", 5, seed)
    x0, y0, x1, y1 = od.bowl_interior(landscape_for(spec))
    for r in spec.rooms:
        assert x0 <= r.center_x - r.width / 2 and r.center_x + r.width / 2 <= x1, r.id
        assert y0 <= r.center_y - r.depth / 2 and r.center_y + r.depth / 2 <= y1, r.id
    report = od.outdoor_dungeon_report(result.eqg_path, spec)
    assert report.passed, report.summary()


@pytest.mark.slow
def test_spawn_stands_on_the_dug_apron(tmp_path):
    """On this seed the Apron's trench runs under the Outdoor_Spawn; the safe
    point kept the undug ground's height and floated 33 u over the floor
    (``safe_point`` failed). It now takes the dug ground's height."""
    spec, result = _outdoor(tmp_path, "temple", 8, 1097127993)
    fmt = check_eqg(result.eqg_path, spec)
    assert fmt.passed, fmt.failed_checks
    # The spec is also the host terrain's: its undug TER, then the Apron.
    grid = od._host_grid(spec, build_wilderness_ter(spec, "host", 1))
    entrance = od.Entrance.from_dict(spec.wilderness[od.DUNGEON_KEY]["entrance"])
    dug, _ = od._apron(grid, entrance)
    sx, sy, sz = spec.safe_point
    undug = float(od._grid_surface(grid.z, grid.origin, grid.res)(sx, sy))
    ground = float(od._grid_surface(dug, grid.origin, grid.res)(sx, sy))
    assert ground < undug - 1.0          # the trench does run under the Spawn
    # (The bowl field and the TER grid differ by a few hundredths.)
    assert sz == pytest.approx(ground, abs=0.1)
