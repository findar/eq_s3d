"""Dungeon verticality task 9 (Requirement 9.2, 9.3; design V10): the gate
sweep on built multi-level zones.

Graph-layout zones are built through the real pipeline (build, walkability
gate, format check, retry on a fresh seed) over a fixed seed list, at each
Verticality setting:

- dungeon x each base set (``classic_eq``, ``warren``) x plain, ``temple``
  and ``fortress`` x several room counts;
- outdoor dungeon x ``classic_eq`` x ``temple`` and ``fortress``;
- a big race (ogre) and the dragon, in a dungeon on both sets and under a
  hill. The dragon under a hill joined in task 19, once its long U-route
  stairs stopped running past the map edge under the boundary (the bowl
  gate read that as a leak); at ``flat`` it still rarely plans
  (EnvelopeFitError, archive follow-up "Giant and dragon outdoor dungeons
  drop rooms"), which only lowers the bar.

Every stacked build (``moderate``, ``dramatic``) must pass within the
pipeline's retry budget. The same plans are built at ``flat`` (step 6's graph
build) on the same attempt seeds (the pipeline draws them from
``random.Random(seed)``), and each stacked setting's first-attempt pass rate
must be no worse than flat's. The rates are printed (``-s`` shows them).

Also here: a stacked build is reproducible (the PFS footer's write time aside,
lessons-learned "Two .eqg writes are never byte-identical"), and task 13's
timing test (Requirement 9.4).

A passing sweep is necessary, not sufficient: nothing here is looked at in the
3D viewer (task 10 does that).
"""

import time
from dataclasses import replace

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder, room_levels
from generators.pipeline import DEFAULT_MAX_ATTEMPTS, generate_validated
from tests.conftest import gated_attempts, gated_key

STACKED = ("moderate", "dramatic")

#: name -> (zone type, base set, theme, race, room counts, sweep seeds,
#: stacked settings). One parametrized case per theme so the default parallel
#: run spreads them over its workers.
SWEEPS = {
    **{f"dungeon-{rs}-{th or 'plain'}": ("dungeon", rs, th, "", (5, 10, 16), range(4), STACKED)
       for rs in ("classic_eq", "warren") for th in ("", "temple", "fortress")},
    **{f"outdoor_dungeon-classic_eq-{th}": ("outdoor_dungeon", "classic_eq", th, "", (3, 5, 8),
                                            range(3), STACKED)
       for th in ("temple", "fortress")},
    **{f"dungeon-{rs}-{race}": ("dungeon", rs, "", race, (8,), range(4), STACKED)
       for rs in ("classic_eq", "warren") for race in ("ogre", "dragon")},
    "outdoor_dungeon-classic_eq-ogre": ("outdoor_dungeon", "classic_eq", "temple", "ogre", (5,),
                                        range(4), ("moderate",)),
    "outdoor_dungeon-classic_eq-dragon": ("outdoor_dungeon", "classic_eq", "temple", "dragon",
                                          (5,), range(4), ("moderate",)),
}


def _fields(zone_type, rule_set, theme, race, rooms, verticality):
    return dict(zone_type=zone_type, room_count=rooms, dungeon_theme=theme, dungeon_race=race,
                layout="graph", rule_set=rule_set, verticality=verticality)


def _plan(zone_type, rule_set, theme, race, rooms, verticality, name="sweep"):
    return ZonePlan(name=name, **_fields(zone_type, rule_set, theme, race, rooms,
                                         verticality)).validate()


#: The pipeline's own timeout per sweep build.
TIMEOUT_S = 600.0

#: One (sweep, room count, sweep seed) per sweep case.
CASES = [(sweep, n, s) for sweep, (_z, _r, _t, _a, counts, seeds, _v) in sorted(SWEEPS.items())
         for n in counts for s in seeds]


def _keys(sweep, rooms, seed):
    """A case's builds, as ``conftest.gated_attempts`` keys, by setting: flat with
    one attempt (step 6's graph build, the bar), each stacked setting with the
    pipeline's retry budget. ``moderate`` is the graph sweep's default build
    (tests/test_graph_layout_build.py) where the two share a case, so it is built
    once for both."""
    zone_type, rule_set, theme, race, _counts, _seeds, stacked = SWEEPS[sweep]
    return {v: gated_key(_fields(zone_type, rule_set, theme, race, rooms, v), seed,
                         1 if v == "flat" else DEFAULT_MAX_ATTEMPTS, TIMEOUT_S)
            for v in ("flat",) + stacked}


@pytest.mark.slow
@pytest.mark.parametrize("sweep, rooms, seed", CASES, ids=[f"{w}-{n}-{s}" for w, n, s in CASES])
def test_stacked_build_passes_within_the_retries(shared_results, sweep, rooms, seed):
    """One case of the sweep: every stacked build passes within the pipeline's
    retry budget. Its flat build is made here too, so the sweep's builds spread
    over the workers; the comparison below reads them."""
    keys = _keys(sweep, rooms, seed)
    got = dict(zip(keys, shared_results.get_many(list(keys.values()), gated_attempts)))
    failed = [v for v, a in got.items() if a is None and v != "flat"]
    assert not failed, f"stacked builds out of retries: {[(v, rooms, seed) for v in failed]}"


@pytest.mark.slow
@pytest.mark.parametrize("sweep", sorted(SWEEPS))
def test_stacked_builds_pass_the_gate_no_worse_than_flat(shared_results, sweep):
    _z, _r, _t, _a, counts, seeds, stacked = SWEEPS[sweep]
    cases = [(n, s) for n in counts for s in seeds]
    by_case = {case: _keys(sweep, *case) for case in cases}
    keys = [k for ks in by_case.values() for k in ks.values()]
    # The case tests above make these builds; whatever none has started yet is
    # made here, from the far end, so this test and they meet in the middle.
    got = dict(zip(keys[::-1], shared_results.get_many(keys[::-1], gated_attempts)))
    runs = {v: {case: got[ks[v]] for case, ks in by_case.items()} for v in ("flat",) + stacked}
    failed = [(v, rooms, seed) for v in stacked for (rooms, seed), a in runs[v].items()
              if a is None]
    first = {v: sum(a == 1 for a in r.values()) for v, r in runs.items()}
    retries = {v: sum(a - 1 for a in runs[v].values() if a) for v in stacked}
    print(f"\n{sweep}: first-attempt " +
          ", ".join(f"{v} {first[v]}/{len(cases)}" for v in runs) +
          "; retries " + ", ".join(f"{v} {retries[v]}" for v in stacked))
    assert not failed, f"stacked builds out of retries: {failed}"
    for v in stacked:
        assert first[v] >= first["flat"], (sweep, v, first)


@pytest.mark.slow
@pytest.mark.parametrize("zone_type, rule_set, theme, race, rooms, verticality, seed", [
    ("dungeon", "warren", "temple", "", 10, "dramatic", 21),
    ("dungeon", "classic_eq", "", "ogre", 8, "moderate", 3),
    ("outdoor_dungeon", "classic_eq", "fortress", "", 5, "moderate", 4),
])
def test_same_inputs_same_eqg(tmp_path, zone_type, rule_set, theme, race, rooms,
                              verticality, seed):
    """V10 / Req 9.3: a stacked build is reproducible (the PFS footer's write
    time aside)."""
    plan = _plan(zone_type, rule_set, theme, race, rooms, verticality, name="vrepro")
    eqgs = []
    for k in range(2):
        spec = plan_to_spec(plan, seed=seed)
        assert len(set(room_levels(spec).values())) > 1, "not a stacked build"
        result = ZoneBuilder(spec).build(output_dir=tmp_path / str(k), write_glb=False)
        eqgs.append(result.eqg_path.read_bytes())
    assert eqgs[0][:-4] == eqgs[1][:-4]


def _timed_generate(tmp_path, verticality, rooms, seed):
    """CPU seconds for one full generate on a pinned seed (the server's path, GLB
    and maps included), and how many Levels the plan has. CPU time, not wall, as
    in test_graph_layout_build."""
    plan = replace(_plan("dungeon", "classic_eq", "", "", rooms, verticality, name="vtime"), walls="built")
    t0 = time.process_time()
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon",
                            zone_id="vtime", seed=seed, output_dir=tmp_path, failure_log=None)
    elapsed = time.process_time() - t0
    assert vb.validated and vb.attempts == 1, (verticality, vb.attempts)
    return elapsed, len(set(room_levels(plan_to_spec(plan, seed=seed)).values()))


@pytest.mark.slow
def test_multi_level_build_time_within_flat_plus_10s(tmp_path):
    """Req 9.4: a 14-room multi-level build takes at most step 6's graph build
    (``flat``, the same inputs) plus 10 s. The best of two runs each,
    alternating, as in ``test_graph_layout_build``."""
    runs = {"flat": [], "dramatic": []}
    levels = {}
    for k in range(2):
        for v in runs:
            elapsed, levels[v] = _timed_generate(tmp_path / f"{v}{k}", v, 14, 8)
            runs[v].append(elapsed)
    assert levels == {"flat": 1, "dramatic": 3}
    flat, dramatic = min(runs["flat"]), min(runs["dramatic"])
    print(f"\n14 rooms, seed 8: flat {flat:.2f} s, dramatic {dramatic:.2f} s")
    assert dramatic <= flat + 10.0, runs
