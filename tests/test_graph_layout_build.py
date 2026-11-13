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

Also here: a graph build's time against a classic build's (Req 8.4); the
same inputs give the same ``.eqg`` (footer aside,
lessons-learned "Two .eqg writes are never byte-identical"), and the two
outdoor-dungeon bugs the sweep found (a room under the map's edge; the
Spawn left floating over the Apron).

A passing sweep is necessary, not sufficient: nothing here is looked at in
the 3D viewer (task 13 does that).
"""

import os
import time

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.rof2check import check_eqg
from generators import outdoor_dungeon as od
from generators.builder import ZoneBuilder
from generators.pipeline import DEFAULT_MAX_ATTEMPTS, generate_validated
from generators.wilderness.build import build_wilderness_ter, landscape_for
from tests.conftest import gated_attempts, gated_key

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
    return ZonePlan(name=name, **_fields(zone_type, layout, rule_set, theme, rooms)).validate()


def _fields(zone_type, layout, rule_set, theme, rooms):
    return dict(zone_type=zone_type, room_count=rooms, dungeon_theme=theme, layout=layout,
                rule_set=rule_set if layout == "graph" else "")


#: The pipeline's own timeout per sweep build.
TIMEOUT_S = 600.0

#: One (sweep, theme, room count, sweep seed) per sweep case.
CASES = [(sweep, t, n, s) for sweep, (_z, _r, themes, counts, seeds) in sorted(SWEEPS.items())
         for t in themes for n in counts for s in seeds]


def _keys(sweep, theme, rooms, seed):
    """A case's two builds, as ``conftest.gated_attempts`` keys: graph with the
    pipeline's retry budget, classic with one attempt. The graph build is the
    vertical sweep's ``moderate`` one (tests/test_vertical_build.py) on the same
    seed, so it is built once for both."""
    zone_type, rule_set = SWEEPS[sweep][:2]
    return (gated_key(_fields(zone_type, "graph", rule_set, theme, rooms), seed,
                      DEFAULT_MAX_ATTEMPTS, TIMEOUT_S),
            gated_key(_fields(zone_type, "classic", "", theme, rooms), seed, 1, TIMEOUT_S))


@pytest.mark.slow
@pytest.mark.parametrize("sweep, theme, rooms, seed", CASES,
                         ids=[f"{w}-{t or 'plain'}-{n}-{s}" for w, t, n, s in CASES])
def test_graph_build_passes_within_the_retries(shared_results, sweep, theme, rooms, seed):
    """One case of the sweep: its graph build passes within the pipeline's retry
    budget. Its classic build is made here too, so the sweep's builds spread over
    the workers; the comparison below reads them."""
    g, _c = shared_results.get_many(_keys(sweep, theme, rooms, seed), gated_attempts)
    assert g is not None, f"graph build out of retries: {(sweep, theme or 'plain', rooms, seed)}"


@pytest.mark.slow
@pytest.mark.parametrize("sweep", sorted(SWEEPS))
def test_graph_builds_pass_the_gate_no_worse_than_classic(shared_results, sweep):
    zone_type, rule_set, themes, counts, seeds = SWEEPS[sweep]
    cases = [(t, n, s) for t in themes for n in counts for s in seeds]
    keys = [k for case in cases for k in _keys(sweep, *case)]
    # The case tests above make these builds; whatever none has started yet is
    # made here, from the far end, so this test and they meet in the middle.
    got = dict(zip(keys[::-1], shared_results.get_many(keys[::-1], gated_attempts)))
    graph, classic, failed = {}, {}, []
    for case in cases:
        g_key, c_key = _keys(sweep, *case)
        graph[case], classic[case] = got[g_key], got[c_key]
        if got[g_key] is None:
            failed.append((case[0] or "plain",) + case[1:])
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


def _outdoor(tmp_path, theme, rooms, seed, race="", verticality="moderate"):
    plan = _plan("outdoor_dungeon", "graph", "classic_eq", theme, rooms)
    plan.dungeon_race = race
    plan.verticality = verticality
    spec = plan_to_spec(plan.validate(), seed=seed)
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
    """On this seed the Apron's trench runs under the Outdoor_Spawn (46 u
    deep there); the safe point used to keep the undug ground's height and
    float over the floor (``safe_point`` failed, first seen on temple seed
    1097127993). It now takes the dug ground's height. Fortress, not temple:
    it has no theme layer, so a layer retune can't move the case away (the
    temple nave fix did once). A troll's: at stock room scale (step 7 task
    17) a human's Tunnel is 15 u tall and its Apron rarely reaches the Spawn;
    a troll's 20 u Tunnel digs a 49 u trench under it on this seed."""
    # Flat: this test is about the trench under the Spawn, not Levels (step 7
    # task 7 stacks the default moderate build and moves its Entrance).
    spec, result = _outdoor(tmp_path, "fortress", 8, 3, race="troll", verticality="flat")
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
    # (The bowl field and the TER grid differ by a few tenths on a trench this steep.)
    assert sz == pytest.approx(ground, abs=0.5)


def _timed_generate(tmp_path, layout, rooms, seed):
    """CPU seconds for one full generate on a pinned seed: plan to spec, build,
    walkability gate, format check, maps and the GLB (the server's path). CPU
    time, not wall: under the parallel suite a wall clock counts the time the
    build waits for a core, which says nothing about the build (as in
    test_walls_build)."""
    plan = _plan("dungeon", layout, "", "", rooms, name="gltime")
    t0 = time.process_time()
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon",
                            zone_id="gltime", seed=seed, output_dir=tmp_path,
                            failure_log=None)
    elapsed = time.process_time() - t0
    assert vb.validated and vb.attempts == 1, (layout, vb.attempts)
    return elapsed


@pytest.mark.slow
def test_graph_build_time_within_classic_plus_10s(tmp_path):
    """Req 8.4: a 14-room graph build takes at most a classic build of the same
    inputs plus 10 s. The best of two runs each, alternating, so a busy machine
    (the thorough run's workers) slows both alike rather than failing one.
    The bar doubles under the parallel suite, as in test_walls_build: there the
    same build cost twice its CPU time alone (graph 18.3 s against 9.9 s)."""
    runs = {"classic": [], "graph": []}
    for k in range(2):
        for layout in runs:
            runs[layout].append(_timed_generate(tmp_path / f"{layout}{k}", layout, 14, 4))
    classic, graph = min(runs["classic"]), min(runs["graph"])
    print(f"\n14 rooms, seed 4: classic {classic:.2f} s, graph {graph:.2f} s")
    budget = 20.0 if os.environ.get("PYTEST_XDIST_WORKER") else 10.0
    assert graph <= classic + budget, runs
