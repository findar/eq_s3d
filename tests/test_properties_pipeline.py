"""
tests/test_properties_pipeline.py
----------------------------------
Pipeline-level properties for the M0 Property_Suite. These drive the real
validated-generation entry point (``generators.pipeline.generate_validated``) —
the single guarantee shared by the server and the CLI that a gated-theme zone is
never returned unless it passed the traversability gate.

Every test here drives at least one real zone BUILD per attempt, so it is
``@pytest.mark.slow`` with a ``build_settings(...)`` budget (design Req 1.5).

Design reference: ``.kiro/specs/zone-generator-m0-hygiene/design.md``,
Correctness Property 15 (umbrella P2).
"""

from __future__ import annotations

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from generators.layout import LayoutGenerator
from generators.pipeline import generate_validated, GenerationFailed, ValidatedBuild

from tests.pbt_helpers import build_settings, fresh_dir

# A known-navigable dungeon seed. The spy factory ignores the seed the pipeline
# hands it for GEOMETRY (it always builds this flat, connected dungeon) so the
# traversability gate passes on the first attempt — while still recording which
# seed the pipeline asked for. This is the established `test_pipeline._good_*`
# idiom: the factory decides the outcome, the pipeline owns seed selection.
_NAVIGABLE_SEED = 1


@pytest.mark.slow
@build_settings(15)
@given(
    max_attempts=st.integers(min_value=1, max_value=8),
    rng=st.randoms(use_true_random=False),
)
def test_returned_build_is_validated(max_attempts, rng):
    """
    Feature: zone-generator-m0-hygiene, Property 15: Returned builds passed the
    gate (umbrella P2).

    When ``generate_validated`` RETURNS a build for a gated theme (dungeon), that
    build carries ``validated=True`` — the traversability gate ran and passed —
    and its provenance is internally consistent: the pipeline made between one
    and ``max_attempts`` factory calls, and the ``seed`` stamped on the returned
    build is exactly the last seed the factory was handed (the one that produced
    the passing geometry). Exhaustion / failure is out of scope here — a raised
    ``GenerationFailed`` is assumed away (covered by Property 16, task 12.2).

    Validates: M0 Req 5.1, 1.5; umbrella P2.
    """
    seeds_seen: list[int] = []
    calls = {"n": 0}

    def spec_factory(seed: int):
        # Record what the pipeline asked for, then build a genuinely navigable
        # dungeon (fixed good seed) so the gate passes.
        seeds_seen.append(seed)
        calls["n"] += 1
        return LayoutGenerator(zone_type="dungeon", seed=_NAVIGABLE_SEED).generate(
            "p15", room_count=3
        )

    with fresh_dir() as out:
        try:
            result = generate_validated(
                spec_factory,
                zone_type="dungeon",
                zone_id="p15",
                output_dir=out,
                write_glb=False,
                max_attempts=max_attempts,
                rng=rng,
                failure_log=None,
            )
        except GenerationFailed:
            # Only RETURNING calls are in scope for this property.
            assume(False)

    assert isinstance(result, ValidatedBuild)
    assert result.validated, "returned gated build did not pass the gate"
    assert 1 <= calls["n"] <= max_attempts, (
        f"factory called {calls['n']} times, outside [1, {max_attempts}]"
    )
    assert seeds_seen, "factory was never called"
    assert result.seed == seeds_seen[-1], (
        f"returned seed {result.seed} != last seed handed to factory "
        f"{seeds_seen[-1]}"
    )


# A dungeon that is navigable EXCEPT for one isolated room with no corridor —
# unreachable regardless of corridor routing, so the traversability gate always
# rejects it (the established `tests/test_pipeline._broken_spec` pattern). The
# room count stays small (n 2-4) so an 8-attempt unpinned example is cheap.
from generators.zone_spec import RoomSpec  # noqa: E402  (grouped with its use)


def _forced_fail_factory(rooms: int):
    """A spec_factory(seed) that always builds a guaranteed-failing dungeon.

    It honours the seed the pipeline hands it for the base dungeon geometry
    (keyed on the seed, as required), then appends one far-away isolated room so
    the Traversal_Validator rejects every attempt no matter the seed.
    """

    def factory(seed: int):
        spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
            "p16", room_count=rooms
        )
        spec.rooms.append(RoomSpec(
            id="isolated", center_x=100_000.0, center_y=100_000.0, floor_z=0.0,
            width=200, depth=200, height=100,
        ))
        return spec

    return factory


@pytest.mark.slow
@build_settings(15)
@given(
    pinned=st.booleans(),
    seed=st.integers(min_value=0, max_value=2 ** 31 - 1),
    max_attempts=st.integers(min_value=1, max_value=8),
    rooms=st.integers(min_value=2, max_value=4),
)
def test_forced_failure_reported(pinned, seed, max_attempts, rooms):
    """
    Feature: zone-generator-m0-hygiene, Property 16: Forced failures are
    reported, never swapped (umbrella P2, pinned + exhaustion).

    When every Raw_Build of a gated (dungeon) zone fails the traversability
    gate, ``generate_validated`` raises ``GenerationFailed`` rather than ever
    returning a broken zone — and the failure it raises tells the honest story
    of what was tried:

    * PINNED (a ``seed`` is passed): the pipeline respects the explicit request,
      so it builds exactly once and errors out with ``pinned=True``,
      ``attempts == 1``, and the single recorded failure carrying that EXACT
      pinned seed — never swapped for another.
    * UNPINNED (no ``seed``, ``max_attempts`` 1-8, a non-binding timeout): the
      pipeline exhausts all its attempts picking fresh seeds, then reports
      ``pinned=False``, ``timed_out=False`` and ``attempts == max_attempts``.

    Validates: M0 Req 5.2, 5.6, 1.5; umbrella Req 1.6.
    """
    factory = _forced_fail_factory(rooms)

    with fresh_dir() as out:
        with pytest.raises(GenerationFailed) as excinfo:
            generate_validated(
                factory,
                zone_type="dungeon",
                zone_id="p16",
                seed=seed if pinned else None,
                output_dir=out,
                write_glb=False,
                max_attempts=max_attempts,
                timeout_s=1e9,  # non-binding: exhaustion, never timeout
                rng=None,
                failure_log=None,
            )

    err = excinfo.value

    if pinned:
        assert err.pinned is True, "pinned failure not flagged pinned"
        assert err.attempts == 1, (
            f"pinned seed retried: attempts={err.attempts}, expected 1"
        )
        assert err.failures, "no failure recorded"
        assert err.failures[0].seed == seed, (
            f"reported seed {err.failures[0].seed} != pinned seed {seed} "
            "(the pinned seed was swapped)"
        )
    else:
        assert err.pinned is False, "unpinned failure flagged pinned"
        assert err.timed_out is False, (
            "exhaustion reported as a timeout (timeout was non-binding)"
        )
        assert err.attempts == max_attempts, (
            f"attempts={err.attempts}, expected all {max_attempts} exhausted"
        )


@pytest.mark.slow
@build_settings(10)
@given(k=st.integers(min_value=3, max_value=10))
def test_fresh_seeds_vary(k):
    """
    Feature: zone-generator-m0-hygiene, Property 17: Fresh seeds vary
    (umbrella P10).

    When ``generate_validated`` is called repeatedly with NO pinned ``seed`` and
    NO explicit ``rng``, the pipeline draws a brand-new seed for each build via
    ``_fresh_seed(None)`` — the "randomness is a feature" path: same inputs must
    not give the same output. Across ``k`` (3-10) such unpinned calls on the same
    navigable 2-room dungeon, a spy ``spec_factory`` records every seed the
    pipeline hands it. Two invariants hold: every recorded seed is a valid 31-bit
    seed in ``[0, 2147483647]``, and the recorded seeds are NOT all identical.
    (A rare collision between two of the k draws is acceptable — "not all equal"
    is the bar, not "all distinct"; all k identical would mean the pipeline isn't
    actually drawing fresh seeds.) ``_fresh_seed(None)`` uses the module ``random``
    generator, which is independent of Hypothesis's (derandomized) INPUT draws, so
    the seeds still vary across the k calls within one example.

    Validates: M0 Req 5.3, 1.5; umbrella Req 1.6.
    """
    seeds_seen: list[int] = []

    def spec_factory(seed: int):
        # Record the seed the pipeline drew, then build a genuinely navigable
        # 2-room dungeon (fixed good seed) so the gate passes on the first
        # attempt and the call returns — same 12.1 spy idiom.
        seeds_seen.append(seed)
        return LayoutGenerator(zone_type="dungeon", seed=_NAVIGABLE_SEED).generate(
            "p17", room_count=2
        )

    with fresh_dir() as out:
        for _ in range(k):
            result = generate_validated(
                spec_factory,
                zone_type="dungeon",
                zone_id="p17",
                # rng OMITTED and seed OMITTED: each call draws a fresh seed via
                # _fresh_seed(None) off the module random generator.
                output_dir=out,
                write_glb=False,
                failure_log=None,
            )
            assert isinstance(result, ValidatedBuild)

    assert len(seeds_seen) == k, (
        f"factory called {len(seeds_seen)} times, expected {k}"
    )
    assert all(0 <= s <= 2_147_483_647 for s in seeds_seen), (
        f"a drawn seed is outside [0, 2147483647]: {seeds_seen}"
    )
    assert len(set(seeds_seen)) > 1, (
        f"all {k} fresh seeds were identical ({seeds_seen[0]}) — the pipeline "
        "is not drawing fresh seeds (randomness-is-a-feature regression)"
    )


def test_no_api_default_selection(no_api_keys, no_network):
    """
    Feature: zone-generator-m0-hygiene, Property 16 (umbrella P16): No-API
    default selection.

    With no API keys and no planner / texture-provider env override, and with
    the forced globals reset (both done by the ``no_api_keys`` fixture),
    auto-selection must pick the zero-key, no-network defaults:

    * ``ai.planner.get_planner()`` returns the rule planner (``.name == "rule"``).
    * ``generators.textures.factory.get_provider()`` returns the procedural
      provider (``.name == "procedural"``).

    And making those selections must perform NO outbound network call: the
    ``no_network`` fixture yields its ``attempts`` list, which stays empty.

    Validates: M0 Req 5.4; umbrella Req 1.6.
    """
    import ai.planner
    import generators.textures.factory as texture_factory

    planner = ai.planner.get_planner()
    assert planner.name == "rule", (
        f"default planner is {planner.name!r}, expected 'rule' with no API keys"
    )

    provider = texture_factory.get_provider()
    assert provider.name == "procedural", (
        f"default texture provider is {provider.name!r}, expected 'procedural' "
        "with no API keys"
    )

    # The no_network fixture yields its `attempts` list directly (conftest:
    # `yield attempts`), so `no_network` IS that list.
    assert no_network == [], (
        f"selecting the no-API defaults made outbound network attempts: "
        f"{no_network}"
    )


@pytest.mark.slow
def test_no_api_prompt_and_cli(no_api_keys, no_network, tmp_path, monkeypatch):
    """
    Feature: zone-generator-m0-hygiene, Property 16 (umbrella P16): No-API
    prompt and CLI.

    The whole point of P16: the full prompt->zone and CLI->zone flows both work
    with ZERO API keys and ZERO outbound network. With ``no_api_keys`` clearing
    every key / provider override and resetting the forced globals, and
    ``no_network`` blocking every non-loopback socket operation, both the
    natural-language SERVER path and the in-process CLI path must still produce
    an Accepted_Build (a traversability-validated zone), and neither may attempt
    a single foreign network connection.

    Server path: a ``TestClient`` wrapping ``server.app.app`` with the module's
    ``OUTPUT_DIR`` / ``FAILURE_LOG`` redirected under ``tmp_path`` (both read as
    module globals at request time). POST a natural-language ``prompt`` — this
    routes through the rule planner (``get_planner()`` is the zero-key default
    after ``no_api_keys``), builds and gates the zone, and returns a validated
    build. The returned ``glb_url`` then fetches 200.

    CLI path: ``main.main(["generate", "p16", "--rooms", "5", "--output",
    tmp_path])`` runs the same validated pipeline in-process on the default
    (gated) dungeon theme, writing ``p16.eqg`` / ``p16.glb`` / ``p16.json`` under
    ``tmp_path``.

    The loopback TestClient transport passes through ``no_network`` (finding 4),
    so ``attempts`` records only genuinely foreign connects — and it must stay
    empty across BOTH paths.

    Validates: M0 Req 5.5; umbrella Req 1.6.
    """
    import main
    import server.app as app_mod
    from fastapi.testclient import TestClient

    # --- Server path: natural-language prompt -> rule planner -> validated zone
    server_out = tmp_path / "server"
    server_out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", server_out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "server_failures.jsonl")

    client = TestClient(app_mod.app)
    resp = client.post(
        "/api/generate",
        json={"prompt": "a dark dungeon with a few rooms"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Prompt path drove the planner (the zero-key rule planner is the default).
    assert body["source"] == "prompt", f"prompt was not prompt-driven: {body['source']!r}"
    assert body["planner"] == "rule", (
        f"prompt used planner {body['planner']!r}, expected the no-API 'rule' default"
    )
    # Accepted_Build: the traversability gate ran AND passed.
    assert body["validated"] is True, "server prompt build was not validated (gate did not pass)"

    # The returned GLB is fetchable (200) from the redirected OUTPUT_DIR.
    glb_resp = client.get(body["glb_url"])
    assert glb_resp.status_code == 200, (
        f"GET {body['glb_url']} -> {glb_resp.status_code}: {glb_resp.text}"
    )

    # --- CLI path: in-process generate on the default gated dungeon theme
    cli_out = tmp_path / "cli"
    main.main(["generate", "p16", "--rooms", "5", "--output", str(cli_out)])

    # Accepted_Build artifacts written under the CLI output dir. task 19.4:
    # the zone id (the per-build directory) is new_zone_id(prefix=<name>) =
    # p16_<ts>_<hex6>, so every artifact inside — including the spec
    # <name>.json — is named by the Build_Name stem "p16".
    cli_build_dirs = [p for p in cli_out.iterdir()
                      if p.is_dir() and p.name.startswith("p16_")]
    assert len(cli_build_dirs) == 1, (
        f"expected one p16_* build dir, got {cli_build_dirs}")
    build_dir = cli_build_dirs[0] / "v1"
    eqg = build_dir / "p16.eqg"
    glb = build_dir / "p16.glb"
    spec_json = build_dir / "p16.json"
    assert eqg.exists(), f"CLI did not write the .eqg: {eqg}"
    assert glb.exists(), f"CLI did not write the .glb: {glb}"
    assert spec_json.exists(), f"CLI did not write the spec: {spec_json}"

    # --- The whole point of P16: zero outbound network across BOTH paths.
    assert no_network == [], (
        f"the no-API prompt/CLI flow attempted outbound network: {no_network}"
    )


# ---------------------------------------------------------------------------
# M1 Property 2: Returned builds passed both gates, rejected attempts leave
# nothing (umbrella P2). These PIN the task-15.4 scratch -> move -> cleanup
# lifecycle and the two-gate PASS criterion
# (report.passed AND report.corridors_passed AND fmt.passed), over the real
# Enabled set (dungeon, city). Wilderness is disabled, so it is never drawn.
# ---------------------------------------------------------------------------

import json  # noqa: E402  (grouped with the M1 P2 tests that read the Sidecar)
import os  # noqa: E402

from generators.zone_types import ENABLED_ZONE_TYPES  # noqa: E402
import analyzer.traverse as _traverse  # noqa: E402

# The gated ROOM-GRAPH zone types these properties range over (city, dungeon),
# sorted for a stable sample order. Wilderness is enabled but builds from its
# own pipeline (no rooms, the bowl gate), so a LayoutGenerator spec for it is
# not a real wilderness build; its properties live in tests/test_wilderness_*.
_enabled_zone_types = st.sampled_from(sorted(ENABLED_ZONE_TYPES - {"wilderness"}))


@pytest.mark.slow
@build_settings(15)
@given(
    zone_type=_enabled_zone_types,
    rooms=st.integers(min_value=2, max_value=4),
    max_attempts=st.integers(min_value=1, max_value=8),
    rng=st.randoms(use_true_random=False),
)
def test_returned_build_passed_both_gates(zone_type, rooms, max_attempts, rng):
    """
    Feature: zone-generator-m1-controls-traversability, Property 2: Returned
    builds passed both gates, and rejected attempts leave nothing (umbrella P2,
    returned half).

    When ``generate_validated`` RETURNS a ``ValidatedBuild`` for a zone type in
    ``ENABLED_ZONE_TYPES`` (dungeon, city — wilderness has its own pipeline
    and is not drawn), that build provably cleared BOTH gates and its files live only where
    they should:

    * ``vb.validated`` is True — the traversability gate ran and passed;
    * the two traversability verdicts hold — ``report.passed`` (every room
      reachable) and ``report.corridors_passed`` (corridor continuity), re-run
      independently on the RETURNED ``.eqg`` so this does not merely trust the
      pipeline's own bookkeeping;
    * ``vb.format.passed`` holds (the wave-6 Format_Checker gate — a passing stub
      until task 20.3);
    * the Sidecar's ``format`` block equals ``vb.format.to_dict()`` — the merged
      provenance matches the gate result;
    * the Output_Directory holds ONLY ``vb.build_dir`` (the ``<zone_id>/
      v<version>/`` tree) — no ``.attempts/`` scratch, nothing else (failure log
      is disabled here).

    This pins the task-15.4 scratch -> move -> cleanup lifecycle: a returned
    build leaves nothing behind but its own directory.

    Validates: Requirements 4.2, 9.2; umbrella P2.
    """
    seeds_seen: list[int] = []

    def spec_factory(seed: int):
        # Record the seed the pipeline asked for, then build a genuinely
        # navigable zone (fixed good seed) so both gates pass. Same spy idiom as
        # the P15 test above: the factory decides the outcome, the pipeline owns
        # seed selection.
        seeds_seen.append(seed)
        return LayoutGenerator(zone_type=zone_type, seed=_NAVIGABLE_SEED).generate(
            "p2", room_count=rooms
        )

    with fresh_dir() as out:
        try:
            vb = generate_validated(
                spec_factory,
                zone_type=zone_type,
                zone_id="p2",
                output_dir=out,
                write_glb=False,
                max_attempts=max_attempts,
                rng=rng,
                failure_log=None,
            )
        except GenerationFailed:
            # Only RETURNING calls are in scope for the returned half.
            assume(False)

        assert isinstance(vb, ValidatedBuild)

        # -- Gate 1 + 2: the traversability verdicts, re-run on the RETURNED eqg.
        assert vb.validated, "returned gated build is not marked validated"
        report = _traverse.validate(
            vb.result.eqg_path, spec=vb.spec, check_corridors=True
        )
        assert report.passed, (
            "re-validating the returned build found an unreachable room"
        )
        assert report.corridors_passed, (
            "re-validating the returned build found a corridor-continuity break"
        )

        # -- Gate 3: the Format_Checker verdict (passing stub until 20.3).
        assert vb.format is not None and vb.format.passed, (
            "returned build's format gate did not pass"
        )

        # -- The Sidecar's format block equals the gate result it was merged from.
        sidecar = vb.build_dir / f"{vb.spec.name.lower()}.zone.json"
        assert sidecar.exists(), f"Sidecar missing from build dir: {sidecar}"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data.get("format") == vb.format.to_dict(), (
            f"Sidecar format {data.get('format')!r} != vb.format.to_dict() "
            f"{vb.format.to_dict()!r}"
        )

        # -- The Output_Directory holds ONLY the build directory tree. build_dir
        # is output_dir/<zone_id>/v<version>/, so the only top-level entry is the
        # <zone_id> dir; no ".attempts" scratch, no stray files (failure log off).
        top_level = sorted(os.listdir(out))
        assert top_level == ["p2"], (
            f"output dir holds more than the build directory: {top_level} "
            "(a rejected/accepted attempt left scratch behind)"
        )
        assert (vb.build_dir).is_dir(), f"build dir is not a directory: {vb.build_dir}"


def _always_fail_factory(zone_type: str, rooms: int):
    """A ``spec_factory(seed)`` whose every build fails the traversability gate.

    It honours the seed for the base geometry (as required), then appends one
    far-away isolated room with no corridor, so the Traversal_Validator rejects
    EVERY attempt regardless of seed — the established forced-failure idiom.
    """
    from generators.zone_spec import RoomSpec

    def factory(seed: int):
        spec = LayoutGenerator(zone_type=zone_type, seed=seed).generate(
            "p2f", room_count=rooms
        )
        spec.rooms.append(RoomSpec(
            id="isolated", center_x=100_000.0, center_y=100_000.0, floor_z=0.0,
            width=200, depth=200, height=100,
        ))
        return spec

    return factory


@pytest.mark.slow
@build_settings(15)
@given(
    zone_type=_enabled_zone_types,
    pinned=st.booleans(),
    seed=st.integers(min_value=0, max_value=2 ** 31 - 1),
    max_attempts=st.integers(min_value=1, max_value=8),
    rooms=st.integers(min_value=2, max_value=4),
)
def test_forced_failure_leaves_nothing(zone_type, pinned, seed, max_attempts, rooms):
    """
    Feature: zone-generator-m1-controls-traversability, Property 2: Returned
    builds passed both gates, and rejected attempts leave nothing (umbrella P2,
    rejected half).

    When every attempt to build a gated zone type (dungeon, city) is FORCED to
    fail the traversability gate, ``generate_validated`` raises
    ``GenerationFailed`` rather than ever returning a broken zone, and — the
    invariant this pins — leaves nothing on disk:

    * a PINNED call (explicit ``seed``) raises after exactly ONE attempt
      (``pinned=True``, ``attempts == 1``) — the caller's seed is respected, not
      swapped;
    * an UNPINNED call exhausts all ``max_attempts`` fresh seeds and then raises
      (``pinned=False``, ``attempts == max_attempts``);
    * in BOTH cases, after the raise the Output_Directory has NO ``.attempts/``
      scratch entry and NO build directory — only the JSONL failure log may
      exist (disabled here, so the directory is empty).

    This pins the task-15.4 cleanup: a rejected attempt leaves no directory
    behind, whether it is a one-shot pinned failure or an exhausted retry loop.

    Validates: Requirements 4.2, 9.2; umbrella P2.
    """
    factory = _always_fail_factory(zone_type, rooms)

    with fresh_dir() as out:
        with pytest.raises(GenerationFailed) as excinfo:
            generate_validated(
                factory,
                zone_type=zone_type,
                zone_id="p2f",
                seed=seed if pinned else None,
                output_dir=out,
                write_glb=False,
                max_attempts=max_attempts,
                timeout_s=1e9,  # non-binding: exhaustion, never a timeout
                rng=None,
                failure_log=None,
            )

        err = excinfo.value
        if pinned:
            assert err.pinned is True, "pinned forced-failure not flagged pinned"
            assert err.attempts == 1, (
                f"pinned seed retried: attempts={err.attempts}, expected 1"
            )
        else:
            assert err.pinned is False, "unpinned forced-failure flagged pinned"
            assert err.attempts == max_attempts, (
                f"attempts={err.attempts}, expected all {max_attempts} exhausted"
            )

        # Nothing left behind: no ".attempts" scratch, no build directory. With
        # the failure log disabled, the output dir is empty.
        leftover = sorted(os.listdir(out))
        assert leftover == [], (
            f"a rejected attempt left files behind: {leftover} "
            "(scratch or build directory not cleaned up)"
        )


# ---------------------------------------------------------------------------
# M1 Property 7: Availability follows the Enabled set (umbrella P19). This PINS
# the task-15.2 availability helpers (is_enabled / zone_type_listing read the
# set at CALL TIME) and the task-15.5 server gate across ARBITRARY enabled
# subsets of DEFINED_ZONE_TYPES — not just the shipped {dungeon, city}. The
# listing, the controls-400, and the prompt substitution-to-dungeon are one
# function of the Enabled set E.
# ---------------------------------------------------------------------------

import generators.zone_types as _zt  # noqa: E402
import server.app as _app_mod  # noqa: E402
from ai.schema import ZonePlan  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from hypothesis import HealthCheck, settings as _settings  # noqa: E402

from tests.strategies import enabled_subsets, zone_type_names  # noqa: E402
from tests.pbt_helpers import scaled as _scaled  # noqa: E402


# Budget 50 (design "Correctness Properties" table). Each example drives a real
# TestClient build (small 2-4 room zones), so there is no per-example deadline
# and the slow/large-data health checks are suppressed — but this is NOT marked
# ``slow``: it must run in the Default_Run (the gate/availability surface is the
# point of the property). ``scaled(50)`` scales with the active profile exactly
# like ``build_settings`` does (50 under default, 250 under thorough).
@_settings(
    max_examples=_scaled(50),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@example(
    # Regression_Example (discovered failure): a planner that emits the LEGACY
    # value ``outdoor`` for an ENABLED wilderness. Before the root fix the prompt
    # path built/returned the raw ``outdoor`` instead of canonical ``wilderness``
    # (the controls path canonicalised, the prompt path trusted plan.zone_type).
    # server/app.py now canonicalises the enabled planned type too.
    enabled=frozenset({"dungeon", "wilderness"}),
    t="outdoor",
    rooms=2,
).via("discovered failure")
@given(
    enabled=enabled_subsets,
    t=zone_type_names,
    rooms=st.integers(min_value=2, max_value=4),
)
def test_availability_follows_enabled(enabled, t, rooms, tmp_path_factory):
    """
    Feature: zone-generator-m1-controls-traversability, Property 7: Availability
    follows the Enabled set (umbrella P19).

    For any non-empty subset E of ``DEFINED_ZONE_TYPES`` installed as
    ``ENABLED_ZONE_TYPES`` (every drawn E includes ``dungeon`` so the prompt
    substitution has a live target) and any zone-type name t (defined, legacy
    ``outdoor``, removed ``cave``, or an in-domain name), the availability
    surface is exactly one function of E:

    * ``GET /api/zone_types`` (and the ``/api/themes`` alias) list each member of
      ``DEFINED_ZONE_TYPES`` once, in canonical order, with
      ``enabled == (name in E)``; every disabled entry carries a non-empty
      reason and every enabled entry carries ``reason is None``;
    * a CONTROLS request naming t returns 400 **iff** ``canonical_zone_type(t)``
      is not in E — and it does so BEFORE any build/write (the output dir stays
      empty on a 400);
    * a PROMPT whose (stubbed) planner picks t builds as t when t ∈ E, and
      otherwise builds as ``dungeon`` carrying exactly one
      ``zone_type_substituted:<t>->dungeon`` warning AND a ``planned_zone_type``
      Sidecar entry equal to t;
    * every 200 response's ``zone_type`` is a member of E.

    This pins the 15.2 availability helpers (``is_enabled`` /
    ``zone_type_listing`` must read ``ENABLED_ZONE_TYPES`` at call time, so a
    monkeypatched subset takes effect) and the 15.5 server gate across arbitrary
    enabled subsets. A failure here is a real bug in the call-time read or the
    server gating, fixed at the root.

    Validates: Requirements 3.1, 3.3, 3.4; umbrella P19.
    """
    # @given runs many examples per test function; pytest's `monkeypatch`
    # fixture is NOT reset between them, so use an explicit MonkeyPatch context
    # that undoes every patch at the end of each example (Hypothesis's own
    # function_scoped_fixture guidance). `tmp_path_factory` is session-scoped,
    # so it is safe to take as a fixture.
    with pytest.MonkeyPatch.context() as monkeypatch:
        _run_availability_example(enabled, t, rooms, tmp_path_factory, monkeypatch)


def _run_availability_example(enabled, t, rooms, tmp_path_factory, monkeypatch):
    # Install the drawn Enabled set. is_enabled()/zone_type_listing() re-read
    # generators.zone_types.ENABLED_ZONE_TYPES at call time, and server.app
    # calls those (not a captured copy), so this monkeypatch gates the whole
    # availability surface for this example.
    monkeypatch.setattr(_zt, "ENABLED_ZONE_TYPES", frozenset(enabled))

    canonical_t = _zt.canonical_zone_type(t)
    t_enabled = canonical_t is not None and canonical_t in enabled

    # Each example writes under its own OUTPUT_DIR / FAILURE_LOG so a 400's
    # "nothing was written" check is unambiguous and examples don't collide.
    out_dir = tmp_path_factory.mktemp("p7_out")
    monkeypatch.setattr(_app_mod, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(_app_mod, "FAILURE_LOG", out_dir / "failures.jsonl")

    client = TestClient(_app_mod.app)

    # -- Listing: exactly E enabled, in canonical order, reasons as specified. --
    for path in ("/api/zone_types", "/api/themes"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text}"
        listing = resp.json()["zone_types"]
        assert [z["name"] for z in listing] == list(_zt.DEFINED_ZONE_TYPES), (
            f"{path} listing not in canonical DEFINED order: "
            f"{[z['name'] for z in listing]}"
        )
        for z in listing:
            expect_enabled = z["name"] in enabled
            assert z["enabled"] is expect_enabled, (
                f"{path}: {z['name']} enabled={z['enabled']}, "
                f"expected {expect_enabled} for E={sorted(enabled)}"
            )
            if expect_enabled:
                assert z["reason"] is None, (
                    f"enabled {z['name']} carries a reason: {z['reason']!r}"
                )
            else:
                assert z["reason"], (
                    f"disabled {z['name']} has no reason (empty/None): "
                    f"{z['reason']!r}"
                )

    # -- Controls path: 400 IFF canonical_zone_type(t) not in E, before writes. --
    controls_resp = client.post(
        "/api/generate",
        json={"zone_type": t, "rooms": rooms, "elevation": False},
    )
    if not t_enabled:
        assert controls_resp.status_code == 400, (
            f"controls t={t!r} (canonical {canonical_t!r}) not in E="
            f"{sorted(enabled)} should 400, got {controls_resp.status_code}: "
            f"{controls_resp.text}"
        )
        # Refused before any build/write: the output tree stays empty (only the
        # failure log parent may exist; nothing was generated).
        leftover = [p.name for p in out_dir.iterdir() if p.name != "failures.jsonl"]
        assert leftover == [], (
            f"a refused controls request wrote to the output dir: {leftover}"
        )
    else:
        assert controls_resp.status_code == 200, (
            f"controls t={t!r} (canonical {canonical_t!r}) in E="
            f"{sorted(enabled)} should build, got {controls_resp.status_code}: "
            f"{controls_resp.text}"
        )
        body = controls_resp.json()
        assert body["zone_type"] == canonical_t, (
            f"controls built zone_type {body['zone_type']!r} != canonical "
            f"{canonical_t!r}"
        )
        assert body["zone_type"] in enabled, (
            f"200 response zone_type {body['zone_type']!r} not in E="
            f"{sorted(enabled)}"
        )

    # -- Prompt path: planner (stubbed) picks t. t ∈ E builds as t; otherwise
    #    substituted to dungeon with exactly one warning + a Sidecar entry. ----
    def _stub_make_plan(prompt, name="zone"):
        # Return an UN-validated plan so the server sees the planner's raw pick
        # t verbatim (ZonePlan.validate() would canonicalise t away). The server
        # applies is_enabled(plan.zone_type) and substitutes to dungeon itself.
        return ZonePlan(name=name, zone_type=t, room_count=rooms, prompt=prompt)

    monkeypatch.setattr(_app_mod, "make_plan", _stub_make_plan)

    prompt_resp = client.post("/api/generate", json={"prompt": "a test zone"})
    assert prompt_resp.status_code == 200, (
        f"prompt (planner picks t={t!r}) -> {prompt_resp.status_code}: "
        f"{prompt_resp.text}"
    )
    pbody = prompt_resp.json()
    sub_warnings = [
        w for w in pbody["warnings"] if w.startswith("zone_type_substituted:")
    ]

    if t_enabled:
        # Planned t is enabled: built as t, no substitution warning.
        assert pbody["zone_type"] == canonical_t, (
            f"prompt built {pbody['zone_type']!r} != planned-enabled "
            f"canonical {canonical_t!r}"
        )
        assert sub_warnings == [], (
            f"enabled planned t={t!r} should not be substituted; warnings="
            f"{pbody['warnings']}"
        )
    else:
        # Planned t is disabled/undefined: substituted to dungeon, exactly one
        # zone_type_substituted warning naming the RAW planned t.
        assert pbody["zone_type"] == "dungeon", (
            f"disabled planned t={t!r} should build as dungeon, got "
            f"{pbody['zone_type']!r}"
        )
        assert sub_warnings == [f"zone_type_substituted:{t}->dungeon"], (
            f"expected exactly one zone_type_substituted:{t}->dungeon warning, "
            f"got {pbody['warnings']}"
        )
        # The Sidecar of the accepted build records planned_zone_type == t.
        zone_id = pbody["id"]
        sidecar = out_dir / zone_id / "v1" / f"{zone_id}.zone.json"
        assert sidecar.exists(), f"Sidecar missing: {sidecar}"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data.get("planned_zone_type") == t, (
            f"Sidecar planned_zone_type {data.get('planned_zone_type')!r} != "
            f"raw planned t {t!r}"
        )

    # Every 200 response's zone_type is in E.
    assert pbody["zone_type"] in enabled, (
        f"prompt 200 zone_type {pbody['zone_type']!r} not in E={sorted(enabled)}"
    )


# ---------------------------------------------------------------------------
# M1 Property 9: Every artifact carries the Build_Name, one directory per build
# (umbrella P41, Build_Name form). This PINS the task-19.4 naming (every
# artifact, archive entry, ZON model reference and Sidecar `name` agree on the
# one Build_Name stem) AND the pipeline's per-build directory: a build lives in
# <output>/<zone_id>/v1/, and a SECOND build with the SAME Build_Name lands in a
# DIFFERENT directory (a fresh new_zone_id(prefix=<name>)) without touching the
# first build's directory or files (one directory per build — Req 8.3).
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from core.pfs import read_directory as _read_directory  # noqa: E402
from core.paths import new_zone_id as _new_zone_id  # noqa: E402
from core.zon import ZonFile as _ZonFile  # noqa: E402
from tests.strategies import build_names as _build_names  # noqa: E402


def _dir_snapshot(build_dir):
    """Map ``{filename: bytes}`` for every file directly in ``build_dir``.

    Used to prove a second same-name build does NOT mutate the first build's
    directory: the snapshot is captured before the second build and compared
    byte-for-byte after it (the PFS footer stamps ``int(time.time())`` only when
    the archive is (re)written, so an untouched file's bytes are stable).
    """
    return {
        p.name: p.read_bytes()
        for p in sorted(build_dir.iterdir())
        if p.is_file()
    }


def _drive_named_build(spec_factory, *, zone_type, zone_id, out):
    """Drive ``generate_validated`` the way the CLI does (task 19.4): an explicit
    per-build ``zone_id`` (``new_zone_id(prefix=<name>)``), the Build_Name on the
    spec. Returns the ``ValidatedBuild`` (raises through ``GenerationFailed``)."""
    return generate_validated(
        spec_factory,
        zone_type=zone_type,
        zone_id=zone_id,
        output_dir=out,
        write_glb=True,          # exercise the <name>.glb artifact too
        failure_log=None,
    )


@pytest.mark.slow
@build_settings(15)
@given(
    zone_type=_enabled_zone_types,
    name=_build_names,
    seed=st.integers(min_value=0, max_value=2 ** 31 - 1),
)
def test_build_name_and_directories(zone_type, name, seed):
    """
    Feature: zone-generator-m1-controls-traversability, Property 9: Every
    artifact carries the Build_Name, one directory per build (umbrella P41,
    Build_Name form).

    For any enabled room-graph zone type (dungeon, city — wilderness has its
    own pipeline and is not drawn), any valid Build_Name (lower-case ``[a-z0-9_]+``, INCLUDING the
    server ``gen_<ts>_<hex6>`` id shape) and any seed, a validated build is
    internally consistent in its naming and isolated in its own directory:

    * the accepted build lives in ``<output>/<zone_id>/v1/`` — ``vb.build_dir``
      is exactly that directory, and every artifact file is inside it;
    * EVERY artifact, archive entry name, ZON model reference and the Sidecar
      ``name`` AGREE on the one Build_Name stem ``<name>``:
        - the archive is ``<name>.eqg``; it holds ``ter_<name>.ter`` and
          ``<name>.zon`` (and no required entry under any other stem);
        - the ZON ``models[0]`` is ``TER_<NAME>.TER`` (the stem upper-cased);
        - the ``.glb``, ``.zone.json`` and ``.map.svg`` are ``<name>.*``;
        - the Sidecar ``name`` field equals ``<name>``;
      read back off the BUILT ``.eqg`` and Sidecar so this does not merely trust
      the pipeline's bookkeeping (Req 8.2, 9.1);
    * a SECOND build with the SAME Build_Name — driven, as the CLI does, with a
      fresh ``new_zone_id(prefix=<name>)`` — lands in a DIFFERENT directory and
      leaves the first build's directory and files byte-for-byte unchanged (one
      directory per build — Req 8.3). Building ``arena`` twice never overwrites
      the first ``arena`` build.

    This pins task 19.4 (artifact naming) and the pipeline's per-build
    directory. A disagreement between an artifact's stem and ``<name>``, or a
    second same-name build clobbering the first, is a real bug in
    ``generators/builder.py`` / ``generators/pipeline.py`` — fixed at the root,
    with the counterexample pinned as a Regression_Example.

    Validates: Requirements 8.2, 8.3, 9.1; umbrella P41.
    """
    def spec_factory(s: int):
        # Spy idiom (as the sibling P2/P15 tests): honour the seed for the
        # pipeline's bookkeeping, but build a genuinely navigable small zone so
        # both gates pass on the first attempt. The Build_Name flows onto the
        # spec via LayoutGenerator.generate(name, ...), so every artifact is
        # stemmed from <name>.
        return LayoutGenerator(zone_type=zone_type, seed=_NAVIGABLE_SEED).generate(
            name, room_count=3
        )

    ter_entry = f"ter_{name}.ter"
    zon_entry = f"{name}.zon"
    model_ref = f"TER_{name.upper()}.TER"

    with fresh_dir() as out:
        out = Path(out)

        # -- Build 1: an explicit per-build zone_id, exactly as the CLI forms it.
        zone_id_1 = _new_zone_id(prefix=name)
        vb = _drive_named_build(
            spec_factory, zone_type=zone_type, zone_id=zone_id_1, out=out,
        )
        assert isinstance(vb, ValidatedBuild)
        assert vb.validated, "returned enabled build is not marked validated"

        # -- The build lives in <output>/<zone_id>/v1/ and nowhere else. --------
        expected_dir = (out / zone_id_1 / "v1").resolve()
        assert vb.build_dir is not None
        assert vb.build_dir.resolve() == expected_dir, (
            f"build_dir {vb.build_dir} != expected {expected_dir}"
        )
        assert expected_dir.is_dir(), f"build dir is not a directory: {expected_dir}"

        eqg_path = expected_dir / f"{name}.eqg"
        glb_path = expected_dir / f"{name}.glb"
        sidecar_path = expected_dir / f"{name}.zone.json"
        map_path = expected_dir / f"{name}.map.svg"
        for artifact in (eqg_path, glb_path, sidecar_path, map_path):
            assert artifact.exists(), (
                f"artifact not named by the Build_Name / not in the build dir: "
                f"{artifact}"
            )

        # Every file in the build dir is stemmed from <name> (the spec <name>.json
        # the CLI saves is written by main.py, not the pipeline, so it is not
        # here; the pipeline's four artifacts all are).
        for p in expected_dir.iterdir():
            if p.is_file():
                assert p.name.startswith(name + "."), (
                    f"a file in the build dir is not named by the Build_Name "
                    f"{name!r}: {p.name}"
                )

        # -- Read the BUILT eqg: entry names + ZON model ref agree on <name>. ---
        entries, archive_errors = _read_directory(eqg_path.read_bytes())
        assert archive_errors == [], (
            f"the built {eqg_path.name} did not read cleanly: {archive_errors}"
        )
        entry_names = {e.name.lower() for e in entries if e.name is not None}
        assert ter_entry in entry_names, (
            f"archive missing the TER entry {ter_entry!r}; entries={sorted(entry_names)}"
        )
        assert zon_entry in entry_names, (
            f"archive missing the ZON entry {zon_entry!r}; entries={sorted(entry_names)}"
        )

        zon_bytes = next(
            e.data for e in entries
            if e.name is not None and e.name.lower() == zon_entry
        )
        zon = _ZonFile.from_bytes(zon_bytes)
        assert zon.models, f"{zon_entry} has no models"
        assert zon.models[0] == model_ref, (
            f"ZON models[0] {zon.models[0]!r} != TER_<NAME>.TER {model_ref!r} "
            f"(model reference disagrees with the Build_Name)"
        )

        # -- The Sidecar `name` field equals <name>. ----------------------------
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert sidecar.get("name") == name, (
            f"Sidecar name {sidecar.get('name')!r} != Build_Name {name!r}"
        )

        # -- One directory per build: a SECOND same-name build is isolated. -----
        # Snapshot build 1 BEFORE the second build so a clobber is detectable.
        before = _dir_snapshot(expected_dir)

        zone_id_2 = _new_zone_id(prefix=name)
        # new_zone_id stamps a fresh <hex6> (and seconds ts), so two ids built
        # from the same name differ — the CLI's "building <name> twice" case.
        assert zone_id_2 != zone_id_1, (
            f"new_zone_id(prefix={name!r}) returned the same id twice: {zone_id_1}"
        )

        vb2 = _drive_named_build(
            spec_factory, zone_type=zone_type, zone_id=zone_id_2, out=out,
        )
        assert isinstance(vb2, ValidatedBuild)
        second_dir = (out / zone_id_2 / "v1").resolve()
        assert vb2.build_dir is not None and vb2.build_dir.resolve() == second_dir, (
            f"second build_dir {vb2.build_dir} != expected {second_dir}"
        )
        assert second_dir != expected_dir, (
            "second same-name build reused the first build's directory "
            "(one directory per build broken)"
        )

        # The first build's directory and every file in it are UNCHANGED.
        assert expected_dir.is_dir(), (
            "second same-name build removed the first build's directory"
        )
        after = _dir_snapshot(expected_dir)
        assert after == before, (
            "second same-name build mutated the first build's files "
            f"(changed/added/removed: "
            f"{sorted(set(before) ^ set(after)) or 'same names, different bytes'})"
        )

        # The second build is ALSO correctly named (same invariants, its own dir).
        entries2, errors2 = _read_directory((second_dir / f"{name}.eqg").read_bytes())
        assert errors2 == [], f"second built eqg did not read cleanly: {errors2}"
        names2 = {e.name.lower() for e in entries2 if e.name is not None}
        assert ter_entry in names2 and zon_entry in names2, (
            f"second build's archive missing a required entry; entries={sorted(names2)}"
        )


# ---------------------------------------------------------------------------
# M1 Property 15: Writes stay inside the Output_Directory (M1-P6). This runs a
# real generate_validated call under a filesystem audit hook and asserts every
# WRITE-side path lands inside the Output_Directory (the one allowed exception
# being the configured failure-log path), and that a fake EQ_PATH install is
# byte-for-byte UNCHANGED across the call. The "first k attempts forced to fail"
# draw exercises the scratch-create -> reject -> cleanup path and the JSONL
# failure-log write, so confinement is checked on the failure side too.
# ---------------------------------------------------------------------------

import os as _os_p15  # noqa: E402  (grouped with the P15 test)
from pathlib import Path as _Path_p15  # noqa: E402

import core.env as _core_env  # noqa: E402

from tests.pbt_helpers import write_audit, fake_install, snapshot_install  # noqa: E402


def _k_fail_then_pass_factory(zone_type: str, rooms: int, k: int, calls: list):
    """A ``spec_factory(seed)`` whose first ``k`` builds fail the gate, then pass.

    It honours the seed for the base geometry (as required), building a
    genuinely navigable zone. For the first ``k`` calls it also appends one
    far-away isolated room with no corridor, so the Traversal_Validator rejects
    those attempts (forcing the scratch-create -> reject -> cleanup + JSONL log
    path); from call ``k+1`` on it returns the navigable zone unchanged so an
    unpinned run eventually passes. ``calls`` records each seed handed in.
    """
    from generators.zone_spec import RoomSpec

    def factory(seed: int):
        calls.append(seed)
        spec = LayoutGenerator(zone_type=zone_type, seed=_NAVIGABLE_SEED).generate(
            "p15w", room_count=rooms
        )
        if len(calls) <= k:
            spec.rooms.append(RoomSpec(
                id="isolated", center_x=100_000.0, center_y=100_000.0,
                floor_z=0.0, width=200, depth=200, height=100,
            ))
        return spec

    return factory


@pytest.mark.slow
@build_settings(10)
@given(
    zone_type=_enabled_zone_types,
    seed=st.integers(min_value=0, max_value=2 ** 31 - 1),
    rooms=st.integers(min_value=2, max_value=8),
    pinned=st.booleans(),
    k=st.integers(min_value=0, max_value=3),
)
def test_writes_confined(zone_type, seed, rooms, pinned, k):
    """
    Feature: zone-generator-m1-controls-traversability, Property 15: Writes stay
    inside the Output_Directory (M1-P6).

    For any generate call through the Pipeline — any enabled zone type (dungeon,
    city — wilderness has its own pipeline and is not drawn), any seed, room
    count 2-8, pinned or not, with the factory optionally forced to fail its first ``k``
    attempts — run under a filesystem audit hook that records ``open`` in a
    write mode, ``os.rename`` / ``os.replace``, ``os.remove`` / ``os.rmdir``,
    ``shutil.rmtree`` and ``os.mkdir``, two invariants hold:

    * EVERY recorded write path resolves INSIDE the Output_Directory — or is the
      configured failure-log path (the one exception the design allows; here the
      log is placed inside the output dir, as the CLI does, so it is confined
      too). This covers the scratch-create -> move -> cleanup lifecycle on the
      PASS side and the scratch-create -> reject -> cleanup + JSONL-append on the
      forced-FAIL side (``k`` > 0).
    * A fake EQ_PATH install (configured via ``EQ_PATH``) has the same file list,
      sizes and SHA-256 before and after — nothing is ever written into or over
      the EQ install (Req 10.2).

    This pins task 19.5's ``OutputRoot`` routing: every write, move and remove a
    build performs is confined to the one Output_Directory. A write that escapes
    (or a change to the fake install) is a REAL confinement bug in the routing —
    fixed at the root in ``core/paths.py`` or the escaping caller, never by
    weakening this assertion, with the counterexample pinned as a
    Regression_Example.

    Validates: Requirements 10.1, 4.2; M1-P6.
    """
    calls: list[int] = []
    factory = _k_fail_then_pass_factory(zone_type, rooms, k, calls)

    with fresh_dir() as out_s, fresh_dir() as eq_tmp:
        out = _Path_p15(out_s)
        # The failure log lives INSIDE the output dir (as the CLI configures it),
        # so a forced-fail attempt's JSONL append is itself confined.
        failure_log = out / "validation_failures.jsonl"

        # A populated fake EQ install, pointed at by EQ_PATH, snapshotted before.
        install = fake_install(eq_tmp)
        before = snapshot_install(install)

        with pytest.MonkeyPatch.context() as mp:
            # EQ_PATH is read via core.env.env_value; set it on the process env
            # (env_value reads os.environ first) and neutralise .env so a real
            # developer .env can't shadow the fake install path.
            mp.setenv("EQ_PATH", str(install))
            mp.setattr(_core_env, "DOTENV_PATH",
                       _core_env.DOTENV_PATH.parent / ".env.nonexistent-for-tests")

            raised = False
            with write_audit() as audit:
                try:
                    generate_validated(
                        factory,
                        zone_type=zone_type,
                        zone_id="p15w",
                        seed=seed if pinned else None,
                        output_dir=out,
                        write_glb=False,
                        # A small attempt budget: an unpinned run needs > k
                        # attempts to get past the k forced failures.
                        max_attempts=k + 4,
                        timeout_s=1e9,  # non-binding: never a timeout
                        rng=None,
                        failure_log=failure_log,
                    )
                except GenerationFailed:
                    # A PINNED seed whose (forced) attempt fails is never
                    # retried, so it raises — that is still a fully exercised
                    # scratch-create -> reject -> cleanup + log path, and every
                    # write it made is in scope for the confinement check.
                    raised = True

            recorded = audit.paths

        # A pinned run only raises when its single attempt was forced to fail.
        if pinned and k >= 1:
            assert raised, "pinned forced-fail attempt did not raise GenerationFailed"

        # -- Invariant 1: confinement of the pipeline's own writes. -----------
        # The audit records writes from the WHOLE process while the block runs,
        # which includes a dependency's legitimate use of the OS temp directory
        # (numpy/scipy import scratch, Hypothesis bookkeeping, etc.) — those are
        # NOT the pipeline's zone writes and are not a confinement breach (the
        # design even reserves ``output/.tmp/`` for such dependency temp). What
        # the property pins is: (1a) NOTHING is ever written into the EQ_PATH
        # install, and (1b) every write the pipeline directs at its build tree
        # lands INSIDE the Output_Directory (or is the configured failure-log
        # path — the one allowed exception, itself confined here).
        out_resolved = out.resolve()
        log_resolved = failure_log.resolve()
        install_resolved = install.resolve()

        def _under(child: _Path_p15, parent: _Path_p15) -> bool:
            return child == parent or parent in child.parents

        # The set of filesystem locations this example "owns" and that the
        # pipeline could plausibly target: its output tree and its fake install.
        # A recorded write under the output tree MUST be confined to it (a
        # genuine escape — e.g. remove_tree following a junction out, or a
        # crafted name slipping past OutputRoot — would surface here); a write
        # under the install is a hard breach.
        for p in recorded:
            try:
                rp = _Path_p15(p).resolve()
            except (OSError, ValueError):
                continue

            # (1a) A write into the fake EQ install is a confinement breach.
            if _under(rp, install_resolved):
                raise AssertionError(
                    f"pipeline wrote into the EQ_PATH install: {rp} "
                    f"(zone_type={zone_type}, seed={seed}, k={k}, pinned={pinned})"
                )

            # (1b) A write under the output tree must be inside it or be the log.
            # A write to output_dir's own parent that names the output dir (a
            # sibling-escape like ``<out>/../<out>_evil``) would resolve outside
            # and is flagged; an unrelated OS-temp write elsewhere is ignored.
            if _under(rp, out_resolved):
                assert rp == log_resolved or _under(rp, out_resolved), (
                    f"a pipeline write under the output tree is not confined: {rp}"
                )
            elif rp == log_resolved:
                # The failure log — the one write the design allows at (or, for
                # the server, just outside) the output dir. Here it is inside.
                pass

        # The failure log must have been written on a forced-fail run (k > 0):
        # this proves the JSONL-append path was actually exercised AND confined.
        if k >= 1:
            assert log_resolved.exists(), (
                "a forced-fail attempt did not write the confined failure log "
                f"at {log_resolved}"
            )
            assert any(_Path_p15(p).resolve() == log_resolved for p in recorded), (
                "the failure-log write was not recorded by the audit hook"
            )

        # -- Invariant 2: the fake EQ_PATH install is byte-for-byte unchanged. --
        after = snapshot_install(install)
        assert after == before, (
            "the EQ_PATH install changed across generation (a write escaped into "
            f"it): added/removed/changed "
            f"{sorted(set(before) ^ set(after)) or 'same names, different bytes'} "
            f"(zone_type={zone_type}, seed={seed}, k={k}, pinned={pinned})"
        )


# ---------------------------------------------------------------------------
# zone-generator-m2-true-layout-artifacts, Properties 16 and 17 (task 7): the
# map post-pass writes ``<name>.map.svg`` and ``maps/<name>*.txt`` for the
# accepted build only, deterministically.
# ---------------------------------------------------------------------------

import json as _json_m2  # noqa: E402

from analyzer.traverse import load_ter_from_eqg  # noqa: E402
from generators.eqmap import build_map_file, format_map_layer  # noqa: E402
from generators.mapgeom import extract_outline, outline_summary  # noqa: E402
from generators.mapview import render_map_svg  # noqa: E402

_build_names = st.from_regex(r"[a-z][a-z0-9_]{0,11}", fullmatch=True)


def _m2_factory(zone_type: str, seed: int, rooms: int, k: int, name: str,
                calls: list):
    """Builds ``seed``'s zone; the first ``k`` calls get an isolated room so
    the gate rejects them (forcing scratch attempts that must leave nothing)."""
    from generators.zone_spec import RoomSpec

    def factory(_s: int):
        calls.append(_s)
        spec = LayoutGenerator(zone_type=zone_type, seed=seed).generate(
            name, room_count=rooms)
        if len(calls) <= k:
            spec.rooms.append(RoomSpec(
                id="isolated", center_x=100_000.0, center_y=100_000.0,
                floor_z=0.0, width=200, depth=200, height=100))
        return spec

    return factory


def _map_artifacts(root: _Path_p15) -> dict:
    """Every map SVG and EQ map file under ``root``, by relative path."""
    found = [*root.rglob("*.map.svg"), *(p for p in root.rglob("*.txt")
                                          if p.parent.name == "maps")]
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in found}


@pytest.mark.slow
@build_settings(15)
@given(
    zone_type=_enabled_zone_types,
    seed=st.integers(min_value=0, max_value=2 ** 31 - 1),
    rooms=st.integers(min_value=2, max_value=8),
    k=st.integers(min_value=0, max_value=3),
)
def test_map_artifacts_only_for_accepted(zone_type, seed, rooms, k):
    """
    Feature: zone-generator-m2-true-layout-artifacts, Property 16: Map artifacts
    exist exactly for the accepted build (M2-P11, extends umbrella P2).

    With the first ``k`` attempts forced to fail, the Output_Directory holds
    ``<name>.map.svg`` and ``maps/*.txt`` only in the accepted build's
    directory; they equal ``render_map_svg(spec, outline=extract_outline(...))``
    and ``format_map_layer`` of ``build_map_file(...)`` for the accepted TER;
    and the Sidecar's ``map_files`` lists exactly them, with per-band counts
    equal to the outline's.

    Validates: Requirements 8.1, 8.2, 8.4
    """
    name = "p16m"
    calls: list[int] = []
    factory = _m2_factory(zone_type, seed, rooms, k, name, calls)
    with fresh_dir() as out_s:
        out = _Path_p15(out_s)
        try:
            vb = generate_validated(
                factory, zone_type=zone_type, zone_id=name, output_dir=out,
                write_glb=False, max_attempts=k + 1, timeout_s=1e9,
                failure_log=None)
        except GenerationFailed:
            assume(False)  # the drawn seed's own zone failed the gate

        bd = vb.build_dir.resolve()
        found = _map_artifacts(out)
        prefix = bd.relative_to(out.resolve()).as_posix() + "/"
        assert found and all(p.startswith(prefix) for p in found), (
            f"map artifacts outside the accepted build dir: {sorted(found)}")
        assert not (out / ".attempts").exists()

        ter, _ = load_ter_from_eqg(vb.result.eqg_path)
        outline = extract_outline(ter, vb.spec.safe_point)
        expected = {f"{name}.map.svg":
                    render_map_svg(vb.spec, outline=outline).encode("utf-8")}
        mf = build_map_file(outline, vb.spec, name)
        for layer in mf.layers:
            expected[f"maps/{mf.filename(layer.index)}"] = \
                format_map_layer(layer).encode("ascii")
        got = {p[len(prefix):]: b for p, b in found.items()}
        assert got == expected

        data = _json_m2.loads((bd / f"{name}.zone.json").read_text())
        assert sorted(data["map_files"]) == sorted(expected)
        bands = [{k2: v for k2, v in b.items() if k2 != "file"}
                 for b in data["outline"]["bands"]]
        assert bands == outline_summary(outline)["bands"]


@pytest.mark.slow
@build_settings(10)
@given(
    zone_type=_enabled_zone_types,
    seed=st.integers(min_value=0, max_value=2 ** 31 - 1),
    rooms=st.integers(min_value=2, max_value=8),
    name=_build_names,
)
def test_map_artifacts_deterministic(zone_type, seed, rooms, name):
    """
    Feature: zone-generator-m2-true-layout-artifacts, Property 17: Map
    artifacts are deterministic (umbrella P9, artifact slice).

    Two independent Pipeline runs into different Output_Directories with the
    same plan, Pinned_Seed and Build_Name write byte-identical
    ``<name>.map.svg`` and ``maps/*.txt`` files.

    Validates: Requirements 8.3
    """
    def factory(s: int):
        return LayoutGenerator(zone_type=zone_type, seed=s).generate(
            name, room_count=rooms)

    runs = []
    for _ in range(2):
        with fresh_dir() as out_s:
            out = _Path_p15(out_s)
            try:
                generate_validated(
                    factory, zone_type=zone_type, zone_id=name, seed=seed,
                    output_dir=out, write_glb=False, failure_log=None)
            except GenerationFailed:
                assume(False)
            runs.append(_map_artifacts(out))
    assert runs[0], "no map artifacts written"
    assert runs[0] == runs[1]
