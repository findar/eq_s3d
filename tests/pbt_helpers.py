"""
tests/pbt_helpers.py
--------------------
Shared helpers for the M0 Property_Suite (see
`.kiro/specs/zone-generator-m0-hygiene/design.md`, "Helpers").

These are deliberately self-contained: they lean on Hypothesis' `settings` /
`HealthCheck` and the production modules, and do NOT import from the sibling
test modules (`tests/conftest.py`, `tests/strategies.py`) to keep the files
independent while they are authored in parallel.

Design note — the `no_network` fixture listed in the design's Helpers table is a
pytest FIXTURE and lives in `tests/conftest.py` (task 2.3), NOT here.
"""

from __future__ import annotations

import contextlib
import math
import struct
import tempfile
from copy import deepcopy
from typing import Dict, List, Set, Tuple

import numpy as np
from hypothesis import HealthCheck, settings

from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import ZoneBuilder
from generators.layout import LayoutGenerator
import ai.expand as _expand
from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner


# ---------------------------------------------------------------------------
# Hypothesis budget helpers
# ---------------------------------------------------------------------------

def scaled(n: int) -> int:
    """
    Per-test example budget: ``n`` percent of the active profile's
    ``max_examples``. Under the default profile (max_examples=100) this returns
    ``n``; under ``thorough`` (max_examples=500) it returns ``5 * n`` — so every
    test scales by exactly 5x with the profile even when it pins its own budget
    (design Req 1.3).
    """
    return n * settings().max_examples // 100


def build_settings(n: int) -> settings:
    """
    Settings for a build-level (``@pytest.mark.slow``) property test: a scaled
    budget, no per-example deadline, and the slow/large-data health checks
    suppressed (a real build is slow and its generated input can be large).
    ``n`` is a percentage in [10, 25] (design Req 1.5).
    """
    assert 10 <= n <= 25, f"build_settings budget {n} out of [10, 25]"
    return settings(
        max_examples=scaled(n),
        deadline=None,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.data_too_large,
        ],
    )


@contextlib.contextmanager
def fresh_dir():
    """
    A fresh temporary output directory per example.

    ``@given`` tests must not take the function-scoped ``tmp_path`` fixture
    (Hypothesis ``function_scoped_fixture`` health check), so each example that
    writes files gets its own directory via this context manager.
    """
    with tempfile.TemporaryDirectory() as d:
        yield d


# ---------------------------------------------------------------------------
# Build + read-back
# ---------------------------------------------------------------------------

def build_raw(spec, out) -> Tuple[object, bytes, bytes]:
    """
    Build ``spec`` into ``out`` (no GLB) and read the TER and ZON back out of
    the produced ``.eqg``.

    Returns ``(BuildResult, ter_bytes, zon_bytes)``. We compare the TER/ZON, and
    NEVER the ``.eqg`` bytes directly, because the PFS footer stamps
    ``int(time.time())`` (so two otherwise-identical archives differ byte-wise).
    """
    result = ZoneBuilder(spec).build(output_dir=out, write_glb=False)
    name = spec.name.lower()
    arc = PfsArchive.from_file(result.eqg_path)
    ter_bytes = arc.get(f"ter_{name}.ter")
    zon_bytes = arc.get(f"{name}.zon")
    assert ter_bytes is not None, f"ter_{name}.ter missing from {result.eqg_path}"
    assert zon_bytes is not None, f"{name}.zon missing from {result.eqg_path}"
    return result, ter_bytes, zon_bytes


# ---------------------------------------------------------------------------
# Shared P1 / M1-P1 build cache (design Default_Run budget lever 1)
# ---------------------------------------------------------------------------

#: Module-level LRU of ``case_key -> TraversalReport``. ``test_raw_navigable``
#: (umbrella P1) and ``test_corridor_continuity`` (M1-P1) draw the IDENTICAL
#: domain (``_raw_navigable_cases`` + the same ``@example`` pins), so without
#: sharing they each build + validate the same ~23 specs — the single most
#: expensive pair in the suite. This cache lets the two tests share ONE build
#: and ONE ``validate(.., check_corridors=True)`` per case (the corridor check
#: is a superset: ``report.passed`` is unchanged by it, so P1 reads the same
#: verdict it would from ``check_corridors=False``). The two tests stay separate
#: with separate assertions (``report.passed`` vs ``report.corridors_passed``),
#: exactly as the design's lever 1 specifies.
#:
#: Bounded so it can't grow without limit across a session; the bound comfortably
#: exceeds one test's example budget + pins, so every M1-P1 lookup hits the entry
#: P1 just built.
_RAW_REPORT_CACHE: "dict[object, object]" = {}
_RAW_REPORT_CACHE_ORDER: "list[object]" = []
_RAW_REPORT_CACHE_MAX = 256


def build_and_validate_raw(spec, key):
    """
    Build ``spec`` raw and validate it with ``check_corridors=True``, memoised
    on ``key`` in a bounded module-level LRU (design budget lever 1).

    Returns the ``TraversalReport``. The first caller for a ``key`` builds the
    zone into a fresh temp dir and runs the full validator; a second caller with
    the same ``key`` (the sibling P1/M1-P1 test) reuses the cached report. The
    report carries both the per-room verdict (``report.passed``) and the
    corridor verdict (``report.corridors_passed``), so each test asserts its own.
    """
    cached = _RAW_REPORT_CACHE.get(key)
    if cached is not None:
        return cached
    with fresh_dir() as out:
        result, _ter_bytes, _zon_bytes = build_raw(spec, out)
        import analyzer.traverse as _T

        report = _T.validate(result.eqg_path, spec=spec, check_corridors=True)
    _RAW_REPORT_CACHE[key] = report
    _RAW_REPORT_CACHE_ORDER.append(key)
    if len(_RAW_REPORT_CACHE_ORDER) > _RAW_REPORT_CACHE_MAX:
        evict = _RAW_REPORT_CACHE_ORDER.pop(0)
        _RAW_REPORT_CACHE.pop(evict, None)
    return report


# ---------------------------------------------------------------------------
# M0 human-pass reproduction (Decision 13)
# ---------------------------------------------------------------------------

#: The two (prompt, seed) inputs a human signed off on at the M0 3D pass. The
#: wave-1 navigability / continuity properties pin these as ``@example``s so the
#: M1 fixes are proven to keep the known-good zones navigable (Req 5.3).
M0_HUMAN_PASS = (
    ("create a dungeon with 30 rooms", 1949459644),
    ("a dungeon with 30 rooms and long halls", 1510177507),
)


def m0_human_spec(entry, verticality=None):
    """
    Turn an ``M0_HUMAN_PASS`` entry into a ``ZoneSpec`` the same way the pipeline
    does: ``RulePlanner().plan(prompt)`` -> ``plan_to_spec(plan, seed)``.

    ``entry`` is a ``(prompt, seed)`` pair. ``verticality`` optionally overrides
    the plan's verticality before expansion (e.g. ``"flat"`` to re-plan a
    known-good zone with no elevation, per the flat-first pass); when ``None``
    the plan's own verticality is kept. The override also sets ``plan.elevation``
    consistently (flat => off, otherwise on), matching the rule-planner's own
    ``elevation = verticality != "flat"`` invariant so ``plan_to_spec`` sees a
    coherent plan.
    """
    prompt, seed = entry
    plan = RulePlanner().plan(prompt)
    if verticality is not None:
        plan.verticality = verticality
        plan.elevation = verticality != "flat"
    return plan_to_spec(plan, seed)


# ---------------------------------------------------------------------------
# Graph / solvability helpers
# ---------------------------------------------------------------------------

def _entrance_id(spec) -> str:
    """Id of the entrance room (role == 'entrance'), or the first room."""
    for r in spec.rooms:
        if r.role == "entrance":
            return r.id
    return spec.rooms[0].id if spec.rooms else ""


def room_graph(spec) -> Dict[str, Set[str]]:
    """
    Undirected adjacency over room ids, derived from
    ``corridors[*].from_room`` / ``to_room``. Every room appears as a key.
    """
    adj: Dict[str, Set[str]] = {r.id: set() for r in spec.rooms}
    for c in spec.corridors:
        a, b = c.from_room, c.to_room
        adj.setdefault(a, set())
        adj.setdefault(b, set())
        if a and b:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def solvable_walk(spec) -> Set[str]:
    """
    Fixpoint reachability walk for the gating-solvability property (P4).

    Start from the entrance. Repeatedly cross any corridor out of a visited
    room when it is either ungated, or its gate's ``key_room_id`` is already
    visited. Returns the set of visited room ids.
    """
    # corridor id -> gate on it (if any)
    gate_by_corridor = {g.corridor_id: g for g in spec.gates}

    visited: Set[str] = set()
    entrance = _entrance_id(spec)
    if entrance:
        visited.add(entrance)

    changed = True
    while changed:
        changed = False
        for c in spec.corridors:
            gate = gate_by_corridor.get(c.id)
            passable = gate is None or gate.key_room_id in visited
            if not passable:
                continue
            # A corridor is crossable from either end once that end is visited.
            for near, far in ((c.from_room, c.to_room), (c.to_room, c.from_room)):
                if near in visited and far and far not in visited:
                    visited.add(far)
                    changed = True
    return visited


# ---------------------------------------------------------------------------
# Elevation run (production function, not a re-implementation)
# ---------------------------------------------------------------------------

def run_for(spec, theme, room_count, size, a, b) -> float:
    """
    The corridor run length that the elevation grade cap is measured against,
    computed by the PRODUCTION ``LayoutGenerator._elevation_run`` (umbrella
    Req 5.4: call the real function, don't re-implement it).

    Builds a generator for ``theme`` with the plan's ``size`` footprint scale
    (``ai.expand._SIZE_SCALE[size]``), applies ``_apply_room_scale(room_count)``
    (which sets ``corridor_width`` — the only generator state ``_route_legs``
    reads), and returns ``gen._elevation_run(a, b)`` for the two rooms ``a`` and
    ``b`` of the corridor under test.

    DEVIATION from the design's listed ``run_for(spec, theme, room_count, size)``
    signature: ``_elevation_run`` needs the two RoomSpec endpoints to compute a
    per-corridor run, so ``a`` and ``b`` are accepted as explicit arguments.
    ``spec`` is kept for parity / future use (currently unused by the run
    computation itself).
    """
    gen = LayoutGenerator(theme)
    gen.size_multiplier = _expand._SIZE_SCALE[size]
    gen._apply_room_scale(room_count)
    return gen._elevation_run(a, b)


# ---------------------------------------------------------------------------
# TER geometry probes
# ---------------------------------------------------------------------------

_COS_40 = math.cos(math.radians(40.0))


def _ter(ter) -> TerFile:
    """Accept either a TerFile or raw TER bytes."""
    if isinstance(ter, (bytes, bytearray)):
        return TerFile.from_bytes(bytes(ter))
    return ter


def _triangles(ter: TerFile) -> List[np.ndarray]:
    """Each triangle as a (3, 3) float array of its three vertex positions."""
    verts = ter.vertices
    tris: List[np.ndarray] = []
    for p in ter.polygons:
        a = verts[p.v1]
        b = verts[p.v2]
        c = verts[p.v3]
        tris.append(np.array(
            [[a.x, a.y, a.z], [b.x, b.y, b.z], [c.x, c.y, c.z]],
            dtype=float,
        ))
    return tris


def _winding_normal(tri: np.ndarray) -> np.ndarray:
    """Unit face normal from triangle winding ((v1->v2) x (v1->v3))."""
    n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
    length = np.linalg.norm(n)
    if length == 0.0:
        return np.array([0.0, 0.0, 0.0])
    return n / length


def upward_faces(ter) -> List[np.ndarray]:
    """
    Triangles whose winding-normal ``nz`` is at least ``cos 40 deg`` — i.e.
    faces flat enough to walk on under the traversability agent's slope cap.
    Returned as (3, 3) numpy arrays of vertex positions.
    """
    t = _ter(ter)
    out: List[np.ndarray] = []
    for tri in _triangles(t):
        n = _winding_normal(tri)
        if n[2] >= _COS_40:
            out.append(tri)
    return out


def ramp_rises(ter) -> List[float]:
    """Rise (max z - min z) of every upward triangle."""
    rises: List[float] = []
    for tri in upward_faces(ter):
        zs = tri[:, 2]
        rises.append(float(zs.max() - zs.min()))
    return rises


def _point_in_triangle_xy(px: float, py: float, tri: np.ndarray, tol: float) -> Tuple[bool, float]:
    """
    Is (px, py) inside the XY projection of ``tri`` (within ``tol``)? If so,
    also return the barycentric-interpolated Z at that point. Returns
    ``(inside, z)``; ``z`` is unspecified when not inside.
    """
    ax, ay = tri[0, 0], tri[0, 1]
    bx, by = tri[1, 0], tri[1, 1]
    cx, cy = tri[2, 0], tri[2, 1]
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(det) < 1e-12:
        return False, 0.0
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    l3 = 1.0 - l1 - l2
    if l1 < -tol or l2 < -tol or l3 < -tol:
        return False, 0.0
    z = l1 * tri[0, 2] + l2 * tri[1, 2] + l3 * tri[2, 2]
    return True, float(z)


def opening_floor_z(ter, x: float, y: float, z_ref: float, band: float,
                    far_z: float | None = None) -> List[float]:
    """
    Z of every upward triangle whose XY closure contains ``(x, y)`` (tolerance
    1e-4) and whose barycentric Z at that point lies within ``z_ref +/- band``
    — the near-end opening floor under ``(x, y)``.

    The probe measures the corridor's OWN near-end opening, at ``z_ref`` (the
    near room's ``floor_z``). ``band`` (``MAX_SEG_RISE``) scopes the window to
    the SEAM so a real step at the opening is <= 2.5 u off and still caught by
    the caller's strict 0.01 u check, while the legitimately-elevated FAR leg of
    a corridor is not mistaken for a non-flush opening.

    ``far_z`` is the FAR room's ``floor_z`` (the other end of this corridor).
    When the corridor's total rise is itself under ``band`` — a SHORT ramped
    corridor — the far room's flat floor slab (and the ramp top that meets it)
    overhangs the near opening XY in projection and falls inside ``z_ref +/-
    band`` even though the opening itself sits exactly on the near floor. Those
    far-end faces are reached by walking UP the corridor's within-grade-cap
    ramp, not by a step at this threshold, so they are not a non-flush opening.
    Faces whose Z at the point equals ``far_z`` (within 0.01 u) AND differs from
    ``z_ref`` are therefore exempted: the window is scoped to the near-end floor.

    This is a correctness SCOPING fix (it measures the actual opening face, the
    near-end floor), NOT a loosened tolerance: a genuine non-flush opening — the
    threshold floor cut above/below ``z_ref`` at a height that is NOT the far
    room's floor — is still returned and still caught by the caller's 0.01 u
    assertion (verified against an injected 1.5 u lip). ``far_z=None`` keeps the
    original behaviour for any caller that does not know the far end.
    """
    out: List[float] = []
    for tri in upward_faces(ter):
        inside, z = _point_in_triangle_xy(x, y, tri, tol=1e-4)
        if not (inside and (z_ref - band) <= z <= (z_ref + band)):
            continue
        # Exempt the FAR room's floor / ramp-top reached via the within-grade
        # corridor ramp (short ramped corridor whose total rise < band).
        if (far_z is not None
                and abs(z - far_z) <= 0.01
                and abs(z - z_ref) > 0.01):
            continue
        out.append(z)
    return out


# ---------------------------------------------------------------------------
# Advisory clearing
# ---------------------------------------------------------------------------

def clear_advisory(spec):
    """
    Deep copy of ``spec`` with every advisory (pacing / content-suggestion)
    field on every room reset to its default, and all gates removed.

    Cleared per room: ``role='standard'``, ``graph_depth=0``,
    ``semantic_type=''``, ``district=0``, ``prop_hints=[]``,
    ``encounter_intent=''``, ``boss=False``. ``gates`` is emptied.

    KEPT: ``room_theme`` and the spec-level ``dungeon_theme`` / ``dungeon_race``
    / ``elemental_tint`` fields — these are realised content (umbrella P5),
    not advisory suggestions, so clearing them would change geometry/textures.
    """
    out = deepcopy(spec)
    for r in out.rooms:
        r.role = "standard"
        r.graph_depth = 0
        r.semantic_type = ""
        r.district = 0
        r.prop_hints = []
        r.encounter_intent = ""
        r.boss = False
    out.gates = []
    return out


# ---------------------------------------------------------------------------
# Low-level bit helpers
# ---------------------------------------------------------------------------

def f32(x: float) -> float:
    """Round ``x`` to IEEE-754 single precision (for bit-equality checks)."""
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def ref_crc(name: str) -> int:
    """
    Independent reference implementation of EQ's PFS filename CRC: a bitwise,
    MSB-first CRC with polynomial 0x04C11DB7, init 0, and NO final XOR, computed
    over ``name.encode('ascii') + b'\\0'``.

    Written WITHOUT ``core.pfs``'s precomputed table on purpose, so a property
    test can cross-check ``core.pfs._filename_crc32`` against a second, fully
    independent derivation (design Req 2.2).
    """
    poly = 0x04C11DB7
    data = name.encode("ascii") + b"\x00"
    crc = 0
    for byte in data:
        crc ^= (byte << 24) & 0xFFFFFFFF
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ poly) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
    return crc & 0xFFFFFFFF
