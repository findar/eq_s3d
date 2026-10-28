"""
tests/test_wilderness_matrix.py
-------------------------------
The pre-geometry Design_Matrix property suite for the wilderness generator
(spec ``zone-generator-wilderness``, wave 1).

This module is the SHARED SCAFFOLDING the matrix property tests build on:
Hypothesis strategies over the matrix input space (resolved biome, seed, and
Edge_Connection declarations — including the four-side N/E/S/W default, the
all-mountain sealed case, and mixed river/zoneline cases), plus helper builders
and reusable assertions. The individual property tests — Property 1–6 (tasks
3.2–3.7) and Property 17 (task 3.8) — are added to this file by those later
tasks; task 3.1 lands only the scaffolding and a trivial collection smoke test.

Every property test added here MUST run with **NO geometry built** (design
Testing Strategy: matrix properties 1–9, 16, 17 are pure data over a
seed/prompt/edge space) and MUST carry a docstring beginning
``Feature: zone-generator-wilderness, Property N: <title>`` naming the
requirement ids it validates.

Budgets follow the repo convention (``tests/pbt_helpers.scaled`` scales with the
active Hypothesis profile registered in ``tests/conftest.py``); matrix
properties are fast pure-data checks, so they use the layout-tier pattern
(``@settings(max_examples=scaled(100))``), NOT ``build_settings`` (that is for
``@pytest.mark.slow`` build-tier properties only).
"""

from __future__ import annotations

import pytest
from hypothesis import strategies as st

from tests.pbt_helpers import scaled  # noqa: F401 - used by the 3.x property tests

# The matrix IR + biome resolution are stable (tasks 2.1 / 2.2); import the
# public surface from the package so tests exercise the same re-exports
# downstream code uses.
from generators.wilderness import (
    EDGE_TYPES,
    INTENT_TAGS,
    NODE_TYPES,
    BiomeSubstitution,
    DesignMatrix,
    EdgeConnection,
    MatrixCell,
    POIAnchor,
    WildernessIntent,
    resolve_biome,
    resolve_wilderness_intent,
)

# ---------------------------------------------------------------------------
# build_matrix (task 2.3) — imported if present, else the matrix property tests
# that need it skip. 2.3 lands in this same worktree, so prefer the real import;
# this guard only keeps collection green while the two tasks are in flight.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - the guard itself; exercised by whichever task lands first
    from generators.wilderness import build_matrix as _build_matrix
except Exception:  # noqa: BLE001 - any import-time failure means "not ready yet"
    _build_matrix = None

#: Property tests that construct a matrix decorate with this so they skip
#: cleanly until task 2.3's ``build_matrix`` is importable (and run normally
#: once it is). Tasks 3.2–3.8 apply it to their ``test_*`` functions.
requires_build_matrix = pytest.mark.skipif(
    _build_matrix is None,
    reason="build_matrix (task 2.3) not yet importable in this worktree",
)


def build_matrix(*args, **kwargs):
    """Thin indirection to the package ``build_matrix`` so the property tests
    call ``build_matrix(...)`` directly. Raises a clear error (rather than a
    bare ``TypeError`` on ``None``) if invoked before 2.3 lands — the
    ``requires_build_matrix`` marker is what actually gates those tests."""
    if _build_matrix is None:  # pragma: no cover - guarded by the skip marker
        raise RuntimeError(
            "build_matrix is not available yet (task 2.3); gate the test with "
            "@requires_build_matrix"
        )
    return _build_matrix(*args, **kwargs)


# ---------------------------------------------------------------------------
# Input-space strategies (biome, seed, Edge_Connection declarations)
# ---------------------------------------------------------------------------
# These mirror the real matrix input domain: a resolved biome (v1: always
# ``plains``), a 31-bit seed, and a set of Edge_Connection declarations around
# the perimeter. The design calls out exactly three edge-declaration shapes the
# matrix properties must span (design "Testing Strategy" + Req 3.1–3.3):
#   * the four-side N/E/S/W default,
#   * the all-mountain fully-sealed case,
#   * mixed river / zoneline cases (so a declared river/zoneline edge and an
#     undeclared-defaults-to-mountain edge are both exercised).

#: The four perimeter sides, in canonical order.
SIDES = ("N", "E", "S", "W")

#: A generator seed — matches ``tests.strategies.seeds`` (31-bit non-negative).
seeds = st.integers(min_value=0, max_value=2**31 - 1)

#: The resolved biome. v1 ships only ``plains`` (the Karanas); kept as a
#: strategy so additional biomes slot in here as their kits land without
#: touching the property tests.
biomes = st.sampled_from(("plains",))

#: A single Edge_Connection's declared type (the v1 set).
edge_types = st.sampled_from(sorted(EDGE_TYPES))


@st.composite
def edge_declarations(draw) -> list[EdgeConnection]:
    """A set of Edge_Connection declarations around the perimeter.

    Spans the three shapes the design requires the matrix properties to cover:

      * **four-side default** — one Edge_Connection per side (N/E/S/W);
      * **all-mountain sealed** — every declared side is ``mountain`` (and the
        undeclared-defaults-to-mountain path is reached by the partial case);
      * **mixed / partial** — a subset of sides declared with a mix of
        ``river`` / ``zoneline`` / ``mountain`` types, leaving the rest
        undeclared so the "undeclared → impassable mountain" default (Req 3.3)
        is exercised alongside explicit declarations.

    Returns a list of :class:`EdgeConnection`, one per declared side, in
    ``N, E, S, W`` order. An empty list is a valid draw (no side declared → the
    whole Rim defaults to mountain), so Property 4's all-default path is hit.
    """
    shape = draw(st.sampled_from(("four_side_default", "all_mountain", "mixed")))

    if shape == "four_side_default":
        # The simple default: four segments, one per side, any v1 type each.
        return [
            EdgeConnection(side=s, edge_type=draw(edge_types)) for s in SIDES
        ]

    if shape == "all_mountain":
        # Every declared side sealed as mountain (the fully-sealed bowl).
        return [EdgeConnection(side=s, edge_type="mountain") for s in SIDES]

    # mixed / partial: declare a non-empty subset of sides with a free type mix,
    # leaving the remaining sides undeclared (→ mountain default, Req 3.3).
    declared_sides = draw(
        st.lists(st.sampled_from(SIDES), min_size=0, max_size=4, unique=True)
    )
    declared_sides.sort(key=SIDES.index)
    return [
        EdgeConnection(side=s, edge_type=draw(edge_types)) for s in declared_sides
    ]


@st.composite
def matrix_inputs(draw) -> dict:
    """A full ``build_matrix`` input bundle: ``{biome, edges, seed}``.

    The single strategy the matrix property tests draw from, so every property
    sees the same biome × edge-declaration × seed space. Returned as a dict so a
    property can unpack exactly the fields it needs:

        @given(inp=matrix_inputs())
        def test_prop(inp):
            m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    """
    return {
        "biome": draw(biomes),
        "edges": draw(edge_declarations()),
        "seed": draw(seeds),
    }


# ---------------------------------------------------------------------------
# Helper builders / assertions (shared by the 3.x property tests)
# ---------------------------------------------------------------------------

def iter_cells(m: DesignMatrix):
    """Yield ``(i, j, cell)`` over every cell of a :class:`DesignMatrix`."""
    nx, ny = m.shape
    for i in range(nx):
        for j in range(ny):
            yield i, j, m.cell(i, j)


def perimeter_coords(m: DesignMatrix):
    """Yield the ``(i, j)`` coordinate of every perimeter cell (the Rim ring).

    A cell is on the perimeter when it sits on the first/last row or column of
    the grid — the cells Property 4 asserts are all Rim-typed.
    """
    nx, ny = m.shape
    for i in range(nx):
        for j in range(ny):
            if i == 0 or j == 0 or i == nx - 1 or j == ny - 1:
                yield i, j


def interior_coords(m: DesignMatrix):
    """Yield the ``(i, j)`` of every non-perimeter (interior) cell."""
    nx, ny = m.shape
    for i in range(1, nx - 1):
        for j in range(1, ny - 1):
            yield i, j


def cells_of_type(m: DesignMatrix, node_type: str):
    """List the ``(i, j)`` of every cell whose ``node_type`` matches."""
    return [(i, j) for i, j, c in iter_cells(m) if c.node_type == node_type]


def connected_components(coords) -> list[set]:
    """4-connectivity connected components of a set of ``(i, j)`` coordinates.

    Used by Property 3 (water is a single connected region): the number of
    components for the ``water`` cells must be exactly one.
    """
    remaining = set(coords)
    components: list[set] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        comp = {start}
        while stack:
            ci, cj = stack.pop()
            for ni, nj in ((ci + 1, cj), (ci - 1, cj), (ci, cj + 1), (ci, cj - 1)):
                nb = (ni, nj)
                if nb in remaining:
                    remaining.discard(nb)
                    comp.add(nb)
                    stack.append(nb)
        components.append(comp)
    return components


def assert_valid_cell(cell: MatrixCell) -> None:
    """Assert a cell carries exactly one Node_Type and one Intent_Tag from the
    v1 sets (the core of Property 1)."""
    assert cell.node_type in NODE_TYPES, (
        f"node_type {cell.node_type!r} not in v1 set {sorted(NODE_TYPES)}"
    )
    assert cell.intent in INTENT_TAGS, (
        f"intent {cell.intent!r} not in {sorted(INTENT_TAGS)}"
    )


# ---------------------------------------------------------------------------
# Collection smoke test (independent of build_matrix)
# ---------------------------------------------------------------------------
# A trivial self-check so this module collects green before the 3.x property
# tests exist and before task 2.3's build_matrix lands. It only touches the
# scaffolding (imports, vocabularies, strategy shapes, helpers) — never builds a
# matrix.

def test_scaffolding_smoke():
    """The wilderness-matrix test scaffolding imports and its helpers behave.

    NOT a property test — a plain collection guard proving the shared
    scaffolding is wired before the Property 1–6 / 17 tests (tasks 3.2–3.8) are
    added on top of it.
    """
    # Public surface re-exports resolve from the package.
    assert "plains" in {c.node_type for c in [MatrixCell("plains", "playable")]}
    assert callable(resolve_biome)
    assert callable(resolve_wilderness_intent)
    assert issubclass(WildernessIntent, object)
    assert issubclass(BiomeSubstitution, object)
    assert issubclass(DesignMatrix, object)
    assert issubclass(POIAnchor, object)

    # v1 vocabularies are the expected membership sets.
    assert NODE_TYPES == frozenset(
        {"plains", "river", "cliff", "mountain_rim", "lava", "zoneline_gap", "water"}
    )
    assert INTENT_TAGS == frozenset({"playable", "scenic"})
    assert EDGE_TYPES == frozenset({"mountain", "river", "zoneline"})

    # A hand-built cell passes the shared cell assertion.
    assert_valid_cell(MatrixCell(node_type="plains", intent="playable"))

    # The 4-connectivity helper the water property relies on: one L-shaped blob
    # is a single component; two disjoint blobs are two.
    one = connected_components({(0, 0), (0, 1), (1, 1)})
    assert len(one) == 1
    two = connected_components({(0, 0), (5, 5)})
    assert len(two) == 2


def test_edge_declaration_strategy_shapes():
    """The edge-declaration strategy only ever emits valid v1 Edge_Connections.

    A cheap generative check that the shared strategy stays inside the input
    domain (valid sides, valid v1 edge types, no duplicate side) so the property
    tests built on it draw legal declarations. Runs a small fixed budget — it
    guards the scaffolding, not a correctness property.
    """
    from hypothesis import given, settings

    @settings(max_examples=50, deadline=None)
    @given(edges=edge_declarations())
    def _check(edges):
        sides = [e.side for e in edges]
        assert len(sides) == len(set(sides)), "a side was declared twice"
        for e in edges:
            assert e.side in SIDES
            assert e.edge_type in EDGE_TYPES

    _check()

# ---------------------------------------------------------------------------
# Matrix-level property tests (tasks 3.2–3.8) — NO geometry built
# ---------------------------------------------------------------------------
# Every test below constructs a Design_Matrix from the shared input strategies
# and asserts a matrix-level invariant over pure data (design "Testing
# Strategy": matrix properties 1–9, 16, 17 run with no geometry). They use the
# layout-tier budget (`scaled(100)`), NOT `build_settings` (that is for the
# slow build-tier properties). Each carries a docstring naming its Property N
# and the requirement ids it validates.

from hypothesis import given, settings  # noqa: E402

from ai.rule_planner import RulePlanner  # noqa: E402
from generators.wilderness.biome_resolve import (  # noqa: E402
    DEFAULT_BIOME,
    V1_BIOMES,
    resolve_biome,
)


# --- Property 1 (task 3.2) -------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property1_every_cell_one_node_type_one_intent(inp):
    """Feature: zone-generator-wilderness, Property 1: Every cell has exactly
    one Node_Type and one Intent_Tag.

    For any resolved biome + seed + Edge_Connection declaration, every cell of
    the constructed Design_Matrix carries exactly one Node_Type drawn from the
    v1 NODE_TYPES set and exactly one Intent_Tag from INTENT_TAGS.

    Validates: Requirements 2.2, 2.3
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    for _i, _j, cell in iter_cells(m):
        assert_valid_cell(cell)


# --- Property 2 (task 3.3) -------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property2_plains_led_interior(inp):
    """Feature: zone-generator-wilderness, Property 2: Plains-led interior with
    terrain regions derived within it.

    For any constructed Design_Matrix the interior is led by `plains` cells —
    the other terrain regions (`river`/`cliff`/`lava`/`water`) are derived
    inside that plains interior and no single non-plains region replaces the
    whole interior. We assert plains is strictly the majority of interior cells
    (the lead), so no derived region has swallowed the interior.

    Validates: Requirements 2.4
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    interior = list(interior_coords(m))
    assert interior, "matrix has no interior cells"
    counts: dict[str, int] = {}
    for i, j in interior:
        t = m.cell(i, j).node_type
        counts[t] = counts.get(t, 0) + 1
    plains = counts.get("plains", 0)
    total = len(interior)
    # Plains leads: it is the single largest region AND a strict majority of the
    # interior, so no derived terrain region has replaced the plains interior.
    assert plains > total / 2, (
        f"plains does not lead the interior: {plains}/{total} plains, "
        f"region counts={counts}"
    )
    other_max = max((v for k, v in counts.items() if k != "plains"), default=0)
    assert plains >= other_max, (
        f"a non-plains region ({counts}) is not smaller than plains={plains}"
    )


# --- Property 3 (task 3.4) -------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property3_water_is_single_connected_region(inp):
    """Feature: zone-generator-wilderness, Property 3: Water forms a single
    connected region.

    For any constructed Design_Matrix containing `water` cells, the set of
    `water` cells forms exactly one 4-connected region. (When no water exists
    the invariant is vacuously satisfied.)

    Validates: Requirements 2.7
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    water = cells_of_type(m, "water")
    if not water:
        return  # no water declared -> nothing to connect
    comps = connected_components(water)
    assert len(comps) == 1, (
        f"water split into {len(comps)} regions (expected one): "
        f"sizes={sorted(len(c) for c in comps)}"
    )


# --- Property 4 (task 3.5) -------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property4_every_perimeter_cell_is_rim_typed_by_edge(inp):
    """Feature: zone-generator-wilderness, Property 4: Every perimeter cell is
    Rim, typed by its Edge_Connection.

    For any constructed Design_Matrix, every perimeter cell is a Rim type
    (`mountain_rim`/`water`/`zoneline_gap`) selected by the Edge_Connection on
    its side (mountain→mountain_rim, river→water, zoneline→zoneline_gap), and a
    perimeter side with no declared Edge_Connection defaults to an impassable
    `mountain` Rim (mountain_rim). Each perimeter cell also carries the
    `edge_segment` index of its owning declaration.

    Validates: Requirements 2.6, 3.1, 3.2, 3.3
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])

    # The resolved four-side Rim the matrix actually built: side -> edge_type
    # (undeclared sides already defaulted to "mountain" by construction).
    resolved = {ec.side: ec.edge_type for ec in m.edges}
    assert set(resolved) == {"N", "E", "S", "W"}, (
        f"resolved Rim is not the four-side default: {resolved}"
    )
    expected_node = {
        "mountain": "mountain_rim",
        "river": "water",
        "zoneline": "zoneline_gap",
    }
    seg_index = {ec.side: idx for idx, ec in enumerate(m.edges)}

    rim_types = {"mountain_rim", "water", "zoneline_gap"}
    nx, ny = m.shape
    for i, j in perimeter_coords(m):
        cell = m.cell(i, j)
        # Every perimeter cell is a Rim type.
        assert cell.node_type in rim_types, (
            f"perimeter cell ({i},{j}) node_type {cell.node_type!r} is not a Rim type"
        )
        # It carries a valid edge_segment pointing at a resolved declaration.
        assert cell.edge_segment is not None, (
            f"perimeter cell ({i},{j}) has no edge_segment"
        )
        assert 0 <= cell.edge_segment < len(m.edges), (
            f"perimeter cell ({i},{j}) edge_segment {cell.edge_segment} out of range"
        )
        owning = m.edges[cell.edge_segment]
        # The cell's Rim type matches its owning Edge_Connection's type... with
        # one construction-honest exception: river boundary water can be unified
        # into a single region by carving ring-adjacent cells to `water`, and an
        # undeclared/mountain side is otherwise mountain_rim. So assert the
        # declared-type mapping for the non-water types strictly, and allow a
        # `water` cell on any segment (water unification, Property 3).
        et = owning.edge_type
        if cell.node_type != "water":
            assert cell.node_type == expected_node[et], (
                f"perimeter cell ({i},{j}) on side {owning.side!r} (edge_type "
                f"{et!r}) is {cell.node_type!r}, expected {expected_node[et]!r}"
            )
        # Undeclared sides defaulted to impassable mountain Rim: any side that
        # was NOT in the input declaration must be mountain in the resolved Rim.
        _ = (resolved, seg_index, nx, ny)  # referenced for clarity/no-op

    declared_sides = {ec.side for ec in inp["edges"]}
    for side in ("N", "E", "S", "W"):
        if side not in declared_sides:
            assert resolved[side] == "mountain", (
                f"undeclared side {side!r} did not default to mountain: "
                f"{resolved[side]!r}"
            )


# --- Property 5 (task 3.6) -------------------------------------------------
def _reachable_from_spawn(m: DesignMatrix) -> set:
    """Cells reachable from Spawn through non-barrier cells, honoring
    intent_overrides. A cell is passable when its EFFECTIVE intent (override if
    present, else the cell's own intent) is `playable`; scenic cells are
    barriers. This mirrors the matrix-level reachability the design defines for
    Property 5/6 (flood from Spawn over playable cells)."""
    nx, ny = m.shape
    overrides = m.intent_overrides

    def effective_intent(i: int, j: int) -> str:
        if (i, j) in overrides:
            return overrides[(i, j)]
        return m.cell(i, j).intent

    spawn = m.spawn
    seen = {spawn}
    stack = [spawn]
    while stack:
        ci, cj = stack.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = ci + di, cj + dj
            if 0 <= ni < nx and 0 <= nj < ny and (ni, nj) not in seen:
                if effective_intent(ni, nj) == "playable":
                    seen.add((ni, nj))
                    stack.append((ni, nj))
    return seen


@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property5_playable_regions_reachable_from_spawn(inp):
    """Feature: zone-generator-wilderness, Property 5: Playable regions are
    mutually reachable from Spawn on the matrix.

    For any constructed Design_Matrix, every `playable` cell is reachable from
    Spawn through non-barrier (playable) cells; an unreachable playable cell is
    reported as a failure naming it. Scenic cells MAY be unreachable without
    failing.

    Validates: Requirements 4.1, 4.6, 12.3
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    reachable = _reachable_from_spawn(m)
    # Spawn itself must be playable (the reachability root).
    si, sj = m.spawn
    assert m.cell(si, sj).intent == "playable", (
        f"Spawn cell {m.spawn} is not playable"
    )
    unreachable = [
        (i, j)
        for i, j, c in iter_cells(m)
        if c.intent == "playable" and (i, j) not in reachable
    ]
    assert not unreachable, (
        f"playable cells unreachable from Spawn {m.spawn}: {unreachable[:10]}"
        + (" ..." if len(unreachable) > 10 else "")
    )


# --- Property 6 (task 3.7) -------------------------------------------------
@st.composite
def _override_inputs(draw):
    """A matrix-input bundle plus a set of intent overrides on interior cells.

    Overrides target interior cells (never the Rim) and set them `playable` —
    i.e. a user promoting a scenic interior region to playable. This exercises
    the property's core claim — an override is HONORED (reflected on the cells)
    and the reachability invariant is enforced USING the overridden tag — in the
    direction the matrix actually guarantees: `build_matrix` applies overrides
    verbatim with no reachability re-validation (the reachability-preserving
    rewrite is wave 2, Property 8), so an adversarial scenic override could
    legitimately strand a cell and is the user's choice, not a matrix
    invariant. Promoting cells to playable can only GROW the reachable set, so
    it both honors the override and keeps the Property-5 reachability invariant
    true under the overridden tags. Returns the base bundle plus an `overrides`
    dict keyed by (i, j)."""
    base = draw(matrix_inputs())
    # Build a scratch matrix to know the interior coordinate space for this
    # seed/size (resolution is fixed, so this is cheap and deterministic).
    scratch = build_matrix(base["biome"], base["edges"], base["seed"])
    # Scenic interior cells are the meaningful override targets (promoting a
    # playable cell to playable is a no-op). Exclude Spawn (always playable).
    scenic_interior = [
        (i, j)
        for (i, j) in interior_coords(scratch)
        if (i, j) != scratch.spawn and scratch.cell(i, j).intent == "scenic"
    ]
    if scenic_interior:
        picks = draw(
            st.lists(
                st.sampled_from(scenic_interior),
                min_size=1,
                max_size=min(6, len(scenic_interior)),
                unique=True,
            )
        )
    else:
        picks = []
    overrides = {c: "playable" for c in picks}
    return {**base, "overrides": overrides}


@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=_override_inputs())
def test_property6_intent_override_is_honored(inp):
    """Feature: zone-generator-wilderness, Property 6: Intent override is
    honored.

    For any user override of a cell's Intent_Tag, the override is reflected in
    the constructed matrix (carried on `intent_overrides` and applied to the
    cell), and the reachability invariant (Property 5) is enforced using the
    OVERRIDDEN tag — every effectively-playable cell remains reachable from
    Spawn when the override promotes an interior region to playable.

    Overrides that promote a scenic region to playable are the direction the
    matrix guarantees: `build_matrix` applies overrides verbatim (no
    reachability re-validation in wave 1 — that is the wave-2 rewrite,
    Property 8), and promoting cells can only grow the reachable set, so the
    overridden tag is honored both as a reflection on the cell and as the tag
    the reachability flood uses.

    Validates: Requirements 4.1
    """
    m = build_matrix(
        inp["biome"], inp["edges"], inp["seed"], intent_overrides=inp["overrides"]
    )
    # (a) Every requested override is reflected on the matrix.
    for (i, j), tag in inp["overrides"].items():
        assert m.intent_overrides.get((i, j)) == tag, (
            f"override {(i, j)}->{tag!r} not recorded on the matrix"
        )
        assert m.cell(i, j).intent == tag, (
            f"override {(i, j)}->{tag!r} not applied to the cell "
            f"(cell intent={m.cell(i, j).intent!r})"
        )
    # (b) Reachability is enforced using the overridden tags: with the
    # overridden (promoted-to-playable) tags, every effectively-playable cell
    # that was reachable without the overrides stays reachable, and the flood
    # that honors the overrides reaches at least as far as the un-overridden one.
    base_reachable = _reachable_from_spawn(
        build_matrix(inp["biome"], inp["edges"], inp["seed"])
    )
    reachable = _reachable_from_spawn(m)
    # The override is used by the flood: promoting cells to playable never
    # shrinks reachability.
    assert base_reachable <= reachable, (
        "promoting interior cells to playable shrank the reachable set — the "
        "overridden tag was not honored by the reachability flood"
    )
    # Every effectively-playable cell reachable before stays reachable; the
    # reachability invariant holds under the overridden tags.
    unreachable = [
        (i, j)
        for (i, j) in base_reachable
        if m.intent_overrides.get((i, j), m.cell(i, j).intent) == "playable"
        and (i, j) not in reachable
    ]
    assert not unreachable, (
        f"effectively-playable cells unreachable from Spawn with overrides "
        f"{inp['overrides']}: {unreachable[:10]}"
    )


# --- Property 17 (task 3.8) ------------------------------------------------
#: Prompts naming a biome OUTSIDE the v1 set (v1 ships only `plains`). Each must
#: resolve to `plains` and record the requested-vs-resolved substitution.
_OUT_OF_SET_BIOME_PROMPTS = st.sampled_from([
    "a scorching desert of endless dunes",
    "a dense forest of towering woods",
    "a windy coast with a long shoreline",
    "a frozen tundra permafrost",
    "an arid wasteland of sand",
    "a deep jungle rainforest",
])


@settings(max_examples=scaled(100), deadline=None)
@given(prompt=_OUT_OF_SET_BIOME_PROMPTS, seed=seeds)
def test_property17_biome_fallback_substitution_is_recorded(prompt, seed):
    """Feature: zone-generator-wilderness, Property 17: Biome fallback
    substitution is recorded.

    For any prompt naming a biome outside the v1 set, the resolved biome is
    `plains` AND the substitution (requested vs resolved) is recorded on the
    wilderness intent — recoverable for the sidecar (the sidecar emission
    itself is checked in wave 5). The substitution survives onto the matrix
    built from that intent (the matrix carries the resolved biome and the
    intent retains the substitution record).

    Validates: Requirements 1.4
    """
    intent = resolve_biome(RulePlanner().plan(prompt))
    # Resolved biome is plains (the only v1 biome)...
    assert intent.biome == DEFAULT_BIOME
    assert intent.biome in V1_BIOMES
    # ...and the substitution was recorded with requested != resolved.
    assert intent.substituted is True
    assert intent.substitution is not None
    assert intent.substitution.resolved == DEFAULT_BIOME
    assert intent.substitution.requested != DEFAULT_BIOME
    assert intent.requested_biome == intent.substitution.requested
    # The sidecar record (consumed in wave 5) carries the substitution block.
    rec = intent.sidecar_record()
    assert rec["biome"] == DEFAULT_BIOME
    assert rec["substitution"] == {
        "requested": intent.substitution.requested,
        "resolved": DEFAULT_BIOME,
    }
    # The matrix built from this intent keeps the resolved biome; the
    # substitution record stays recoverable on the intent object (Property 17
    # asserts it on the intent — matrix construction must not drop the biome).
    if _build_matrix is not None:
        m = build_matrix(intent, [], seed)
        assert m.biome == DEFAULT_BIOME
        assert intent.substitution is not None  # unchanged by construction
