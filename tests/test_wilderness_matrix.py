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
