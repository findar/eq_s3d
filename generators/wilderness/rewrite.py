"""
generators/wilderness/rewrite.py
--------------------------------
Graph_Replacement over terrain regions (roadmap step 1, Requirement 7).

This is the **matrix-level** rewrite layer: it refines a finished
:class:`~generators.wilderness.matrix.DesignMatrix` by applying rewrite rules
over the terrain ``Node_Type`` vocabulary, preserving two invariants at EVERY
committed step — **playable-reachability** from Spawn (R7.3) and the **sealed
Rim** on every non-``zoneline`` segment (R7.4). NO geometry is built here; the
Noise_Pass / Erosion / upsample are wave 3, the bowl mesh + built-mesh gate are
wave 4. The rewrite stays entirely inside the wilderness module — it does NOT
import or depend on a dungeon ``LayoutEngine`` or a typed-edge seam (those are
roadmap step 6 and do not exist on ``master``).

The design (design.md, "Component: Graph_Replacement over terrain regions") maps
one-to-one onto the three layers in this file:

1. **Region graph** (task 5.2) — :func:`build_region_graph`. A node is a
   connected (4-neighbour) set of same-``node_type`` cells, so rules reason
   about "the cliff region" / "the river", not single cells. Edges are a small
   typed relation set: ``borders`` (regions touch), ``approaches`` (a graded
   ramp/pass provides a playable approach), ``flows_into`` (river → off-map /
   junction). Wilderness-local only.

2. **Termination-bounded rewrite** (task 5.3) — :func:`rewrite_matrix`. Runs to
   a fixed point under a HARD iteration cap (``max_iters = C * region_count``);
   exceeding the cap raises :class:`RewriteError`, never a silent loop (R7.2).
   Each rule is monotone-bounded. **Apply-then-check-then-commit:** a rule is
   applied to a CANDIDATE matrix, both invariants are re-checked, and the
   application is REJECTED (prior matrix kept) if a playable region became
   stranded OR a non-``zoneline`` Rim segment was breached (R7.3/7.4/7.6).
   ``intent_overrides`` are honored in the reachability relation.

3. **The v1 terrain rules** (task 5.4) — :func:`cliff_graded_approach` and
   :func:`lava_graded_approach`. ``cliff → graded approach`` (R7.5): when a
   ``cliff`` region would strand a playable region, carve a ``plains`` corridor
   through/around the cliff carrying an ``approaches`` edge, committed only
   together with its approach so reachability is restored AT that step. The same
   apply-check-commit discipline is applied to a ``lava`` region that would
   strand a playable region (preserve a playable approach around lava, R10.4).

Open Decision resolved here (recorded in task 5.4's Deliverables):

  **v1 rule set:** exactly two rules — ``cliff → graded approach`` and
  ``lava → graded approach``. Rivers stay boundary-hugging in v1 (interior
  tributaries are an explicit out-of-scope fast-follow — Out of scope,
  requirements.md), so NO river-growth / tributary rule ships. ``mountain_rim``
  / ``zoneline_gap`` / ``water`` / ``plains`` are never rule TRIGGERS — the Rim
  is a construction invariant the rewrite must preserve, not rewrite.

  **Fixed-point order:** cliffs are resolved before lava. Within a type,
  trigger regions are taken in sorted (anchor-cell) order. Rationale: a cliff is
  a structural framing band that can strand a whole flank of the interior, while
  v1 lava is a compact interior patch; resolving the larger structural stranding
  first minimizes rework, and the deterministic order makes the fixed point
  reproducible for a given seed (R16). The loop re-scans from the start after
  every committed change, so ordering only affects which equivalent fixed point
  is reached, never whether one is reached.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from generators.wilderness.matrix import DesignMatrix, MatrixCell

Coord = Tuple[int, int]

# ---------------------------------------------------------------------------
# Vocabulary shared across the three layers
# ---------------------------------------------------------------------------

#: Node types that block playable traversal when a cell carries the default
#: (un-overridden) ``scenic`` intent. These are the scenic blockers the
#: reachability flood must route around. ``river`` is NOT a barrier in v1 (it
#: hugs the boundary and is crossed/forded as plains-adjacent ground at the
#: matrix level); ``mountain_rim``/``water`` are the sealed Rim, ``lava`` is the
#: interior hazard, ``cliff`` is the scenic framing band.
_BARRIER_NODE_TYPES: FrozenSet[str] = frozenset(
    {"mountain_rim", "water", "lava", "cliff"}
)

#: Node types a rule is allowed to carve a graded approach THROUGH / replace with
#: a playable ``plains`` corridor. The Rim (``mountain_rim``/``water`` edges and
#: ``zoneline_gap``) is never carved by a rule — sealing it is an invariant.
_RULE_TRIGGER_TYPES: Tuple[str, ...] = ("cliff", "lava")

_NEIGHBORS4: Tuple[Coord, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))

#: Iteration-cap constant: ``max_iters = C * region_count`` (R7.2). Each
#: committed rule consumes one trigger region (monotone), so the number of
#: committed steps is bounded by the trigger-region count; ``C`` gives headroom
#: for rejected candidates and the fixed-point re-scan without ever permitting an
#: unbounded loop.
MAX_ITERS_C: int = 8


class RewriteError(RuntimeError):
    """Raised when the bounded rewrite exceeds its hard iteration cap (R7.2).

    Exceeding ``max_iters = C * region_count`` is a construction error, never a
    silent loop — a monotone-bounded rewrite that does not terminate signals a
    rule that fails to consume its trigger, which is a bug to surface loudly.
    """


# ===========================================================================
# Layer 1 (task 5.2): the region graph over the terrain vocabulary
# ===========================================================================


@dataclass
class Region:
    """A connected (4-neighbour) set of same-``node_type`` matrix cells.

    A region is the unit a rewrite rule reasons about ("the cliff region", "the
    river"), not a single cell. ``rid`` is a stable within-graph id; ``cells``
    is the frozen set of matrix coordinates; ``anchor`` is the lexicographically
    smallest cell (deterministic identity for ordering / id assignment).
    """

    rid: int
    node_type: str
    cells: FrozenSet[Coord]
    anchor: Coord

    @property
    def size(self) -> int:
        return len(self.cells)


@dataclass
class RegionEdge:
    """A typed relation between two regions.

    ``relation`` is one of:
      - ``borders`` — the two regions touch (share a 4-neighbour boundary).
      - ``approaches`` — a graded ramp/pass provides a playable approach between
        the regions (spawned by the ``cliff/lava → graded approach`` rule).
      - ``flows_into`` — a ``river`` region reaches an off-map / junction sink
        (a boundary ``zoneline_gap``/``water`` edge, i.e. the river leaves the
        map). Wilderness-local; no interior river junctions in v1.
    """

    a: int
    b: int
    relation: str


@dataclass
class RegionGraph:
    """The region graph of a :class:`DesignMatrix`.

    Nodes are :class:`Region`s keyed by ``rid``; ``edges`` is the typed relation
    set. ``cell_region`` maps every matrix coordinate to its owning ``rid`` so
    rules can look up "which region is this cell in" in O(1). Purely a read
    model over a matrix snapshot — rebuilt after each committed rewrite step.
    """

    regions: Dict[int, Region]
    edges: List[RegionEdge]
    cell_region: Dict[Coord, int]
    shape: Tuple[int, int]

    def regions_of_type(self, node_type: str) -> List[Region]:
        """All regions of ``node_type``, in deterministic anchor order."""
        out = [r for r in self.regions.values() if r.node_type == node_type]
        out.sort(key=lambda r: r.anchor)
        return out

    def borders(self, rid: int) -> List[int]:
        """Region ids that ``borders`` region ``rid`` (either direction)."""
        out: Set[int] = set()
        for e in self.edges:
            if e.relation != "borders":
                continue
            if e.a == rid:
                out.add(e.b)
            elif e.b == rid:
                out.add(e.a)
        return sorted(out)


def _in_bounds(i: int, j: int, nx: int, ny: int) -> bool:
    return 0 <= i < nx and 0 <= j < ny


def build_region_graph(matrix: DesignMatrix) -> RegionGraph:
    """Build the region graph from ``matrix`` (task 5.2, R7.1).

    A node is a maximal 4-connected set of cells sharing a ``node_type``. Edges
    are the typed relation set:

    - ``borders`` between any two regions that share a 4-neighbour boundary;
    - ``flows_into`` from each ``river`` region to a sink it reaches — a
      boundary ``zoneline_gap`` or boundary ``water`` region (the river leaves
      the map). Modeled as a river→sink edge; there are no interior river
      junctions in v1 (rivers hug the boundary).

    ``approaches`` edges are not derived from a static matrix here — they are
    SPAWNED by the graded-approach rule (task 5.4) when it carves a corridor, and
    recorded on the graph rebuilt after that commit via :func:`_approach_edges`.
    This function does, however, recover existing ``approaches`` relations: a
    ``plains`` corridor that a prior rule carved adjacent to a ``cliff``/``lava``
    region is re-expressed as an ``approaches`` edge so the relation is stable
    across rebuilds.
    """
    nx, ny = matrix.shape
    cell_region: Dict[Coord, int] = {}
    regions: Dict[int, Region] = {}

    # --- connected-components flood over same-type cells ------------------
    next_rid = 0
    for si in range(nx):
        for sj in range(ny):
            start = (si, sj)
            if start in cell_region:
                continue
            node_type = matrix.cells[si, sj].node_type
            comp: List[Coord] = [start]
            cell_region[start] = next_rid
            q = deque([start])
            while q:
                ci, cj = q.popleft()
                for di, dj in _NEIGHBORS4:
                    ni, nj = ci + di, cj + dj
                    if not _in_bounds(ni, nj, nx, ny):
                        continue
                    nb = (ni, nj)
                    if nb in cell_region:
                        continue
                    if matrix.cells[ni, nj].node_type != node_type:
                        continue
                    cell_region[nb] = next_rid
                    comp.append(nb)
                    q.append(nb)
            anchor = min(comp)
            regions[next_rid] = Region(
                rid=next_rid,
                node_type=node_type,
                cells=frozenset(comp),
                anchor=anchor,
            )
            next_rid += 1

    # --- typed edges ------------------------------------------------------
    edges: List[RegionEdge] = []

    # borders: dedup unordered pairs of distinct adjacent regions.
    border_pairs: Set[Tuple[int, int]] = set()
    for (ci, cj), rid in cell_region.items():
        for di, dj in _NEIGHBORS4:
            ni, nj = ci + di, cj + dj
            if not _in_bounds(ni, nj, nx, ny):
                continue
            other = cell_region[(ni, nj)]
            if other == rid:
                continue
            border_pairs.add((min(rid, other), max(rid, other)))
    for a, b in sorted(border_pairs):
        edges.append(RegionEdge(a=a, b=b, relation="borders"))

    # flows_into: each river region -> a boundary sink it borders (a boundary
    # zoneline_gap region or a boundary water region). v1 rivers hug the
    # boundary, so a river region typically reaches the Rim directly.
    edges.extend(_flows_into_edges(matrix, regions, cell_region, border_pairs))

    # approaches: recover from the matrix — a plains region bordering BOTH a
    # trigger-type region and the rest of the interior is a carved/natural pass.
    edges.extend(_approach_edges(regions, cell_region, border_pairs))

    return RegionGraph(
        regions=regions, edges=edges, cell_region=cell_region, shape=(nx, ny)
    )


def _is_boundary_region(region: Region, nx: int, ny: int) -> bool:
    """Whether any cell of ``region`` lies on the matrix perimeter."""
    for (i, j) in region.cells:
        if i in (0, nx - 1) or j in (0, ny - 1):
            return True
    return False


def _flows_into_edges(
    matrix: DesignMatrix,
    regions: Dict[int, Region],
    cell_region: Dict[Coord, int],
    border_pairs: Set[Tuple[int, int]],
) -> List[RegionEdge]:
    """``flows_into`` edges: river region → the boundary sink it reaches.

    A sink is a boundary ``zoneline_gap`` or boundary ``water`` region (the
    river leaving the map). If a river borders no distinct sink region (it is
    itself the boundary water), it ``flows_into`` the off-map directly, modeled
    as a self-edge sink id of ``-1``.
    """
    nx, ny = matrix.shape
    out: List[RegionEdge] = []
    rivers = [r for r in regions.values() if r.node_type == "river"]
    for river in sorted(rivers, key=lambda r: r.anchor):
        sink: Optional[int] = None
        for a, b in border_pairs:
            if river.rid not in (a, b):
                continue
            other = b if a == river.rid else a
            o = regions[other]
            if o.node_type in ("zoneline_gap", "water") and _is_boundary_region(
                o, nx, ny
            ):
                sink = other
                break
        if sink is None:
            # No distinct boundary sink: the river itself reaches the perimeter
            # (it IS the boundary) -> flows off-map (sink id -1).
            if _is_boundary_region(river, nx, ny):
                out.append(RegionEdge(a=river.rid, b=-1, relation="flows_into"))
        else:
            out.append(RegionEdge(a=river.rid, b=sink, relation="flows_into"))
    return out


def _approach_edges(
    regions: Dict[int, Region],
    cell_region: Dict[Coord, int],
    border_pairs: Set[Tuple[int, int]],
) -> List[RegionEdge]:
    """``approaches`` edges recovered from the matrix.

    A ``plains`` region that borders a ``cliff`` or ``lava`` region expresses an
    ``approaches`` relation: it is a playable pass alongside/through the scenic
    blocker. This is the stable re-expression of what the graded-approach rule
    carves, so the relation survives a graph rebuild after a commit.
    """
    out: List[RegionEdge] = []
    for a, b in sorted(border_pairs):
        ra, rb = regions[a], regions[b]
        pair = {ra.node_type, rb.node_type}
        if "plains" in pair and (pair & {"cliff", "lava"}):
            out.append(RegionEdge(a=a, b=b, relation="approaches"))
    return out


# ===========================================================================
# Layer 2 (task 5.3): invariants + the termination-bounded rewrite
# ===========================================================================


def _effective_intent(matrix: DesignMatrix, i: int, j: int) -> str:
    """Effective intent of cell ``(i, j)`` honoring ``intent_overrides`` (R4.1).

    An override promotes the cell to the overridden tag (wave-1 contract: an
    override of a scenic interior cell to ``playable`` is honored and can only
    GROW reachability). Absent an override the cell's own ``intent`` applies.
    """
    ov = matrix.intent_overrides.get((i, j))
    if ov is not None:
        return ov
    return matrix.cells[i, j].intent


def _is_passable(matrix: DesignMatrix, i: int, j: int) -> bool:
    """Whether the reachability flood may traverse cell ``(i, j)``.

    A cell is passable when its EFFECTIVE intent is ``playable``. The default
    scenic blockers (``mountain_rim``/``water``/``lava``/``cliff``) are scenic
    and therefore impassable unless an ``intent_override`` promotes them; a
    ``plains``/``zoneline_gap``/``river`` cell is playable unless an override
    demotes it. This is the single reachability relation both the gate check and
    the rules consult, so "honor intent_overrides" holds uniformly (R7.3).
    """
    return _effective_intent(matrix, i, j) == "playable"


def playable_reachable_from_spawn(matrix: DesignMatrix) -> Set[Coord]:
    """Cells reachable from Spawn over passable (effective-``playable``) cells.

    Honors ``intent_overrides`` via :func:`_is_passable`. Spawn itself is the
    root; if Spawn is not passable the reachable set is empty (a degenerate
    matrix the invariant check below will treat as "everything stranded").
    """
    nx, ny = matrix.shape
    spawn = matrix.spawn
    if not _is_passable(matrix, spawn[0], spawn[1]):
        return set()
    seen: Set[Coord] = {spawn}
    q = deque([spawn])
    while q:
        ci, cj = q.popleft()
        for di, dj in _NEIGHBORS4:
            ni, nj = ci + di, cj + dj
            if not _in_bounds(ni, nj, nx, ny):
                continue
            nb = (ni, nj)
            if nb in seen:
                continue
            if _is_passable(matrix, ni, nj):
                seen.add(nb)
                q.append(nb)
    return seen


def stranded_playable_cells(matrix: DesignMatrix) -> Set[Coord]:
    """Playable cells NOT reachable from Spawn (the stranded set, R7.3/R4.6).

    A cell is "playable" for this check by its effective intent. The returned
    set is empty iff every playable cell is mutually reachable from Spawn.
    """
    nx, ny = matrix.shape
    reachable = playable_reachable_from_spawn(matrix)
    stranded: Set[Coord] = set()
    for i in range(nx):
        for j in range(ny):
            if _is_passable(matrix, i, j) and (i, j) not in reachable:
                stranded.add((i, j))
    return stranded


def rim_is_sealed(matrix: DesignMatrix) -> bool:
    """Whether every non-``zoneline`` Rim segment is still impassable (R7.4).

    A perimeter cell belongs to an ``Edge_Connection`` via ``edge_segment``. A
    ``zoneline`` segment is the deliberate leak; every OTHER perimeter cell must
    stay a sealed Rim type — ``mountain_rim`` or boundary ``water`` (whose
    impassability comes from the Invisible_Wall / ridge realized downstream). If
    a rule carved a perimeter cell to a passable type on a non-``zoneline``
    segment, the Rim is breached.
    """
    nx, ny = matrix.shape
    seg_type: Dict[int, str] = {k: e.edge_type for k, e in enumerate(matrix.edges)}
    for i in range(nx):
        for j in range(ny):
            if not (i in (0, nx - 1) or j in (0, ny - 1)):
                continue
            cell = matrix.cells[i, j]
            seg = cell.edge_segment
            etype = seg_type.get(seg) if seg is not None else None
            if etype == "zoneline":
                continue  # the deliberate leak
            # Non-zoneline Rim cell: must remain a sealed Rim node type.
            if cell.node_type not in ("mountain_rim", "water"):
                return False
    return True


def invariants_hold(matrix: DesignMatrix) -> bool:
    """Both committed-step invariants: no stranded playable region AND the Rim
    sealed on every non-``zoneline`` segment (R7.3 + R7.4)."""
    return not stranded_playable_cells(matrix) and rim_is_sealed(matrix)


def _clone_matrix(matrix: DesignMatrix) -> DesignMatrix:
    """A deep-enough copy to serve as a rewrite CANDIDATE.

    Cells are copied (a rule mutates cell node_type/intent/frozen), but scalar
    config and the edge list are shared read-only. Uses the matrix's own
    ``to_dict``/``from_dict`` round-trip so the clone is independent and cannot
    alias the live grid — the key property apply-check-commit relies on (a
    rejected candidate must not have touched the prior matrix).
    """
    return DesignMatrix.from_dict(matrix.to_dict())


@dataclass
class RewriteResult:
    """The outcome of :func:`rewrite_matrix` (diagnostics for tests / logging).

    ``matrix`` is the fixed-point matrix (the prior matrix if nothing applied).
    ``committed`` counts committed rule applications; ``rejected`` counts
    apply-check-commit rejections; ``iterations`` counts loop passes; ``steps``
    records a ``(rule_name, trigger_anchor, committed)`` tuple per attempt so a
    property test can assert the invariants held at every committed step.
    """

    matrix: DesignMatrix
    committed: int = 0
    rejected: int = 0
    iterations: int = 0
    steps: List[Tuple[str, Coord, bool]] = field(default_factory=list)


def rewrite_matrix(matrix: DesignMatrix, *, max_iters: Optional[int] = None) -> RewriteResult:
    """Run Graph_Replacement to a fixed point (tasks 5.3 + 5.4).

    Termination-bounded apply-then-check-then-commit:

    1. Build the region graph; enumerate applicable rule TRIGGERS in the fixed
       v1 order (cliffs before lava, anchor order within a type).
    2. For the first trigger whose region currently strands a playable region,
       apply its rule to a CANDIDATE clone.
    3. Re-check BOTH invariants on the candidate. If they hold AND the stranded
       set strictly shrank, COMMIT (the candidate becomes the live matrix) and
       re-scan from the top. Otherwise REJECT (keep the prior matrix) and mark
       that trigger region resolved so the loop makes progress (monotone).
    4. Stop at a fixed point (no applicable trigger) or raise
       :class:`RewriteError` if the hard cap ``max_iters = C * region_count`` is
       exceeded (R7.2) — never a silent loop.

    The invariants hold at EVERY committed step because a candidate that would
    strand a playable region or breach a non-``zoneline`` Rim segment is never
    committed (R7.3/R7.4/R7.6). ``intent_overrides`` are honored throughout via
    the shared :func:`_is_passable` relation.
    """
    current = matrix
    graph = build_region_graph(current)
    region_count = max(1, len(graph.regions))
    cap = max_iters if max_iters is not None else MAX_ITERS_C * region_count

    result = RewriteResult(matrix=current)

    # Trigger regions already visited (by anchor+type) so a rejected or
    # non-improving application is not retried forever — this is what makes the
    # bound monotone: every pass either commits (shrinking the stranded set) or
    # retires a trigger.
    resolved: Set[Tuple[str, Coord]] = set()

    while True:
        if result.iterations > cap:
            raise RewriteError(
                f"Graph_Replacement exceeded the iteration cap "
                f"(max_iters={cap}, region_count={region_count}); a rule failed "
                f"to consume its trigger — refusing to loop silently (R7.2)."
            )
        result.iterations += 1

        trigger = _next_trigger(current, graph, resolved)
        if trigger is None:
            break  # fixed point: no applicable rule remains

        rule_name, region = trigger
        resolved.add((region.node_type, region.anchor))

        candidate = _clone_matrix(current)
        rule = _RULES[rule_name]
        changed = rule(candidate, region)

        prior_stranded = stranded_playable_cells(current)
        if changed and invariants_hold(candidate):
            new_stranded = stranded_playable_cells(candidate)
            if len(new_stranded) < len(prior_stranded):
                # Commit: reachability strictly improved and both invariants hold.
                current = candidate
                graph = build_region_graph(current)
                result.committed += 1
                result.steps.append((rule_name, region.anchor, True))
                # A commit can change region ids/anchors; clear resolved markers
                # for still-unresolved triggers so newly-exposed stranding is
                # retried. Monotone because the stranded set strictly shrank.
                resolved = _carry_resolved(current, resolved)
                continue

        # Reject: keep the prior matrix (R7.6). Record the rejected attempt.
        result.rejected += 1
        result.steps.append((rule_name, region.anchor, False))

    result.matrix = current
    return result


def _carry_resolved(
    matrix: DesignMatrix, resolved: Set[Tuple[str, Coord]]
) -> Set[Tuple[str, Coord]]:
    """After a commit, keep only resolved-markers whose trigger region still
    exists with the same anchor — so genuinely consumed triggers are not
    retried, but regions reshaped by the carve are re-examined."""
    graph = build_region_graph(matrix)
    live = {(r.node_type, r.anchor) for r in graph.regions.values()}
    return {m for m in resolved if m in live}


def _next_trigger(
    matrix: DesignMatrix,
    graph: RegionGraph,
    resolved: Set[Tuple[str, Coord]],
):
    """The next applicable ``(rule_name, region)`` in the fixed v1 order.

    A trigger is applicable iff its region currently STRANDS at least one
    playable cell — i.e. removing/approaching it is what reachability needs.
    Only triggers that actually strand a playable region fire, so a matrix that
    is already fully reachable reaches an immediate fixed point (no spurious
    rewrites). Cliffs are considered before lava; anchor order within a type.
    """
    stranded = stranded_playable_cells(matrix)
    if not stranded:
        return None
    for node_type in _RULE_TRIGGER_TYPES:
        for region in graph.regions_of_type(node_type):
            if (region.node_type, region.anchor) in resolved:
                continue
            if _region_strands_playable(matrix, region, stranded):
                return (_RULE_FOR_TYPE[node_type], region)
    return None


def _region_strands_playable(
    matrix: DesignMatrix, region: Region, stranded: Set[Coord]
) -> bool:
    """Whether ``region`` is (part of) what strands a playable cell.

    A scenic blocker region "strands" when it 4-borders a currently-stranded
    playable cell — removing/approaching it is a candidate for reconnecting that
    cell. This keeps the rewrite targeted: only blockers adjacent to the stranded
    frontier are tried, not every cliff/lava on the map.
    """
    nx, ny = matrix.shape
    for (ci, cj) in region.cells:
        for di, dj in _NEIGHBORS4:
            ni, nj = ci + di, cj + dj
            if _in_bounds(ni, nj, nx, ny) and (ni, nj) in stranded:
                return True
    return False


# ===========================================================================
# Layer 3 (task 5.4): the v1 terrain rules
# ===========================================================================


def _carve_plains(cell: MatrixCell) -> None:
    """Turn a cell into a playable ``plains`` approach cell.

    The carved corridor is ordinary playable ground: the grade/subdivision is
    the heightfield's job downstream (the TER grid is already fine — the M1
    ramp-subdivision lesson binds the dungeon BOX backend, not this matrix), so
    the matrix just records a ``plains`` + ``playable`` cell and drops any
    frozen-Z constraint the blocker carried.
    """
    cell.node_type = "plains"
    cell.intent = "playable"
    cell.frozen = False
    cell.frozen_z = None


def _interior_border_cells(
    matrix: DesignMatrix, region: Region
) -> List[Coord]:
    """Interior (non-perimeter) cells of ``region`` — the only cells a rule may
    carve. Carving a perimeter cell could breach the Rim, so rules work strictly
    inside the interior; the Rim stays sealed by never being a carve target."""
    nx, ny = matrix.shape
    out = [
        (i, j)
        for (i, j) in region.cells
        if not (i in (0, nx - 1) or j in (0, ny - 1))
    ]
    out.sort()
    return out


def _graded_approach(matrix: DesignMatrix, region: Region) -> bool:
    """Shared body of the ``cliff``/``lava`` → graded-approach rules.

    Carve a ``plains`` corridor through the blocker region so the stranded
    playable cells on one side reconnect to Spawn's side. v1 carves the WHOLE
    interior footprint of the triggering region to ``plains`` (a graded approach
    that replaces the blocker band with playable ground). Because the region is
    small and plains-led (Property 2), this is a bounded addition keyed to the
    v1 feature count (R7.2 monotone bound): it consumes the trigger region
    entirely. Returns ``True`` if it carved anything.

    The carve is validated by the caller's apply-check-commit — it is applied to
    a candidate and only committed if BOTH invariants then hold and reachability
    improved, so a carve that would breach the Rim (it never targets perimeter
    cells) or fail to reconnect is rejected and the prior matrix kept (R7.6).
    """
    targets = _interior_border_cells(matrix, region)
    if not targets:
        return False
    for (i, j) in targets:
        _carve_plains(matrix.cells[i, j])
    return True


def cliff_graded_approach(matrix: DesignMatrix, region: Region) -> bool:
    """``cliff → graded approach`` (R7.5).

    When a ``cliff`` region would strand a playable region, carve a ``plains``
    corridor through/around the cliff (carrying an ``approaches`` edge, which the
    rebuilt region graph re-expresses via :func:`_approach_edges`) so the
    stranded region reconnects to Spawn. Committed only together with its
    approach — the caller's apply-check-commit guarantees reachability is
    restored AT this step or the application is rejected.
    """
    return _graded_approach(matrix, region)


def lava_graded_approach(matrix: DesignMatrix, region: Region) -> bool:
    """``lava → graded approach`` (R10.4).

    The same apply-check-commit discipline as cliffs: when a ``lava`` region
    would strand a playable region, preserve a playable approach around the lava
    by carving a ``plains`` corridor so no playable region is stranded by lava.
    The lava MESH realization (impassable + damaging) lands in wave 4; here the
    rule only guarantees a playable approach exists at the matrix level.
    """
    return _graded_approach(matrix, region)


#: Rule dispatch: node type -> rule name, and rule name -> callable. The fixed
#: v1 order lives in ``_RULE_TRIGGER_TYPES`` (cliffs before lava).
_RULE_FOR_TYPE: Dict[str, str] = {
    "cliff": "cliff_graded_approach",
    "lava": "lava_graded_approach",
}
_RULES = {
    "cliff_graded_approach": cliff_graded_approach,
    "lava_graded_approach": lava_graded_approach,
}


__all__ = [
    "RewriteError",
    "Region",
    "RegionEdge",
    "RegionGraph",
    "build_region_graph",
    "RewriteResult",
    "rewrite_matrix",
    "playable_reachable_from_spawn",
    "stranded_playable_cells",
    "rim_is_sealed",
    "invariants_hold",
    "cliff_graded_approach",
    "lava_graded_approach",
]
