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
from hypothesis import assume, given
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

    # Accepted_Build artifacts written under the CLI output dir. task 15.4
    # moves accepted builds into <zone_id>/v<version>/; the .eqg/.glb live
    # there now, while main.py still saves the spec flat for inspection.
    build_dir = cli_out / "p16" / "v1"
    eqg = build_dir / "p16.eqg"
    glb = build_dir / "p16.glb"
    spec_json = cli_out / "p16.json"
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

# The gated zone types this property ranges over. Sorted for a stable sample
# order; wilderness is absent from ENABLED_ZONE_TYPES, so this is (city,
# dungeon) and the property never touches a disabled type (task note).
_enabled_zone_types = st.sampled_from(sorted(ENABLED_ZONE_TYPES))


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
    ``ENABLED_ZONE_TYPES`` (dungeon, city — wilderness is disabled and never
    drawn), that build provably cleared BOTH gates and its files live only where
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
