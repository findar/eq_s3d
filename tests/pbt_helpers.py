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


# ---------------------------------------------------------------------------
# M1-P6 filesystem-confinement audit (Property 15)
# ---------------------------------------------------------------------------
#
# ``write_audit`` installs ONE module-level ``sys.addaudithook`` (audit hooks
# can never be removed, so it is added exactly once and guarded by a module
# flag) that records the path argument of every WRITE-side filesystem audit
# event while recording is enabled, and is completely inert otherwise. The
# Property-15 test turns recording on around a single ``generate_validated``
# call and then asserts every recorded path resolved inside the
# Output_Directory.
#
# Audit events (CPython runtime audit events) and the path argument we capture:
#   * ``open``            (path, mode, flags) — recorded only when ``mode``
#                         contains a write/append/create/truncate intent
#                         (``w`` ``a`` ``x`` ``+``) or the raw ``os.open`` flags
#                         request write/create/truncate; a pure read ``open`` is
#                         ignored.
#   * ``os.rename``       (src, dst)   — both endpoints recorded.
#   * ``os.replace``      — CPython emits this under the ``os.rename`` event.
#   * ``os.mkdir``        (path, mode) — recorded.
#   * ``os.remove``       (path)       — recorded (``os.unlink`` emits this too).
#   * ``os.rmdir``        (path)       — recorded.
#   * ``shutil.rmtree``   (path)       — recorded (not used by the confined
#                         pipeline, but watched so a regression that reaches for
#                         it is caught).
#   * ``pathlib.Path.*``  — ``Path.write_bytes`` / ``write_text`` / ``mkdir`` /
#                         ``unlink`` / ``rename`` / ``replace`` all go through the
#                         ``open`` / ``os.*`` events above at the C level, so they
#                         are covered without a separate hook.
#
# Only the WRITE side is watched (design: "records ``open`` in a write mode,
# ``os.rename``, ``os.replace``, ``os.remove``, ``os.rmdir``, ``shutil.rmtree``
# and ``os.mkdir``"); a read-only ``open`` is deliberately not recorded so the
# hook does not drown the measured region in every stat/read the build performs.

import os as _os
import sys as _sys
import threading as _threading
from pathlib import Path

# Write-intent character classes for a text ``open`` mode string.
_WRITE_MODE_CHARS = frozenset("waxWAX+")

# The os.open integer-flag bits that mean "this descriptor can be written".
_WRITE_OPEN_FLAGS = (
    _os.O_WRONLY | _os.O_RDWR | _os.O_APPEND | _os.O_CREAT | _os.O_TRUNC
    | getattr(_os, "O_EXCL", 0)
)

#: Module-level recording state for the single audit hook. ``enabled`` gates
#: recording (the hook is inert when False); ``paths`` accumulates the recorded
#: write paths; ``lock`` guards both so a threaded server request is safe.
_AUDIT_STATE = {
    "enabled": False,
    "paths": [],  # type: List[str]
    "installed": False,
}
_AUDIT_LOCK = _threading.Lock()


def _audit_is_write_open(args) -> bool:
    """Whether an ``open`` audit event's ``(path, mode, flags)`` is a write."""
    # args is (path, mode, flags). mode is a str like "w"/"rb"/"a+" or None;
    # flags is the integer passed to os.open (0 for the builtin open with a
    # mode string).
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else 0
    if isinstance(mode, str) and any(c in _WRITE_MODE_CHARS for c in mode):
        return True
    if isinstance(flags, int) and (flags & _WRITE_OPEN_FLAGS):
        return True
    return False


# Audit events whose FIRST argument is a path we always record when they fire
# in the measured region (write-side mutations).
_PATH_EVENTS = frozenset({
    "os.mkdir", "os.rmdir", "os.remove", "os.unlink", "shutil.rmtree",
    "shutil.copyfile", "shutil.copytree", "shutil.move",
})
# Rename/replace carry TWO paths (src, dst); CPython emits os.replace under the
# os.rename event name.
_RENAME_EVENTS = frozenset({"os.rename", "os.replace", "os.link", "os.symlink"})


def _audit_hook(event: str, args) -> None:
    """The one module-level audit hook. Inert unless recording is enabled.

    Appends the path(s) of each write-side event to ``_AUDIT_STATE['paths']``
    while ``enabled`` is set. Never raises (an audit hook that raises would
    abort the audited operation), and does the cheapest possible check first so
    it adds no measurable cost outside the measured region.
    """
    if not _AUDIT_STATE["enabled"]:
        return
    try:
        if event == "open":
            if _audit_is_write_open(args):
                _audit_record(args[0] if args else None)
            return
        if event in _RENAME_EVENTS:
            for target in args[:2]:
                _audit_record(target)
            return
        if event in _PATH_EVENTS:
            _audit_record(args[0] if args else None)
            return
    except Exception:
        # Never abort the audited operation because of a hook hiccup.
        return


def _audit_record(target) -> None:
    """Append ``target`` to the recorded paths as a ``str`` filesystem path.

    Skips ``None`` and integer file descriptors (not a confine-checkable path);
    decodes a bytes path to ``str``. Anything else is coerced through
    ``os.fspath`` and ``str``.
    """
    if target is None or isinstance(target, int):
        return
    try:
        p = _os.fspath(target)
    except TypeError:
        return
    if isinstance(p, bytes):
        p = _os.fsdecode(p)
    _AUDIT_STATE["paths"].append(str(p))


def _ensure_audit_installed() -> None:
    """Install the single audit hook exactly once (idempotent, thread-safe)."""
    with _AUDIT_LOCK:
        if not _AUDIT_STATE["installed"]:
            _sys.addaudithook(_audit_hook)
            _AUDIT_STATE["installed"] = True


@contextlib.contextmanager
def write_audit():
    """Record every WRITE-side filesystem path while the block runs.

    Installs the one module-level audit hook on first use (it can never be
    removed, so it is guarded to install once and stays inert outside this
    block), clears the recorded-path list, enables recording for the duration
    of the ``with`` block, and yields an object with a ``.paths`` property
    returning the list of recorded paths (as strings) captured so far. Recording
    is disabled again on exit, so the hook adds no cost to the rest of the suite.

    Usage::

        with write_audit() as audit:
            ... # run the measured region
        for p in audit.paths:
            assert inside_output_dir(p)
    """
    _ensure_audit_installed()

    class _Recorder:
        @property
        def paths(self):
            # A copy so callers can iterate while (in principle) more is added.
            return list(_AUDIT_STATE["paths"])

    with _AUDIT_LOCK:
        _AUDIT_STATE["paths"] = []
        _AUDIT_STATE["enabled"] = True
    try:
        yield _Recorder()
    finally:
        with _AUDIT_LOCK:
            _AUDIT_STATE["enabled"] = False


# ---------------------------------------------------------------------------
# Fake EQ install (M1-P6 untouched-install check)
# ---------------------------------------------------------------------------

import hashlib as _hashlib


def fake_install(tmp) -> Path:
    """Create a small fake EQ install directory tree under ``tmp``.

    Writes a handful of files with known contents (mimicking an EQ_PATH install:
    a couple of top-level archives and a nested subdirectory) and returns the
    install root. Pair with :func:`snapshot_install` to assert the install is
    byte-for-byte UNCHANGED across a generate call (Property 15 / Req 10.2:
    nothing is ever written into or over the EQ_PATH install).
    """
    root = Path(tmp) / "fake_eq_install"
    root.mkdir(parents=True, exist_ok=True)
    (root / "gfaydark.s3d").write_bytes(b"S3D\x00" + b"fake zone archive bytes" * 4)
    (root / "qeynos.eqg").write_bytes(b"PFS \x00" + bytes(range(64)))
    (root / "spells_us.txt").write_text("1|Fake Spell|0|0|\n", encoding="utf-8")
    nested = root / "maps"
    nested.mkdir(exist_ok=True)
    (nested / "qeynos.map").write_text("L 0 0 0 1 1 1 255 255 255\n", encoding="utf-8")
    return root


def snapshot_install(root: Path):
    """A snapshot of ``root``'s tree: ``{relpath: (size, sha256)}`` per file.

    Captures every file under ``root`` (relative path, byte size, and SHA-256 of
    its contents) so two snapshots — before and after a generate call — can be
    compared for exact equality. Any added, removed, resized or rewritten file
    makes the two snapshots differ.
    """
    root = Path(root)
    snap: Dict[str, Tuple[int, str]] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            data = p.read_bytes()
            rel = str(p.relative_to(root)).replace("\\", "/")
            snap[rel] = (len(data), _hashlib.sha256(data).hexdigest())
    return snap


# ---------------------------------------------------------------------------
# M2 outline oracles (definitional Floor_Boundary, reference depth bands)
# ---------------------------------------------------------------------------
#
# Independent of ``generators/mapgeom.py``: these test the Floor_Boundary by
# its definition (a Floor_Region edge point whose 0.05 u outward probe lies in
# no Floor_Region face within the 3 u step-up), sample by sample, against every
# region triangle. Design: ``.kiro/specs/zone-generator-m2-true-layout-artifacts/
# design.md``, Testing Strategy "Helpers".

ORACLE_PROBE = 0.05
ORACLE_STEP_UP = 3.0


def _region_tris(ter, region) -> np.ndarray:
    t = _ter(ter)
    V = np.array([[v.x, v.y, v.z] for v in t.vertices], dtype=float).reshape(-1, 3)
    F = np.array([[p.v1, p.v2, p.v3] for p in t.polygons], dtype=np.int64).reshape(-1, 3)
    return V[F[np.asarray(region, bool)]]


def _region_edges(tris: np.ndarray):
    """Every region face edge as (A, B, outward unit XY normal)."""
    A = tris[:, [0, 1, 2]].reshape(-1, 3)
    B = tris[:, [1, 2, 0]].reshape(-1, 3)
    C = tris[:, [2, 0, 1]].reshape(-1, 3)
    d = B[:, :2] - A[:, :2]
    out = np.stack([d[:, 1], -d[:, 0]], axis=1)
    ln = np.linalg.norm(out, axis=1)
    ok = ln > 1e-12
    A, B, C, out = A[ok], B[ok], C[ok], out[ok] / ln[ok, None]
    flip = np.einsum("ij,ij->i", C[:, :2] - A[:, :2], out) > 0
    out[flip] *= -1.0
    return A, B, out


ORACLE_CELL = 32.0     # bucket size (u) for the oracle's spatial grid


def _cell_of(xy: np.ndarray) -> np.ndarray:
    return np.floor(xy / ORACLE_CELL).astype(np.int64)


def _boxes_by_cell(lo: np.ndarray, hi: np.ndarray):
    """``{cell: indices}`` of the axis-aligned XY boxes overlapping each cell.
    A bucketing only: every test stays exact on the pairs it returns."""
    c0, c1 = _cell_of(lo), _cell_of(hi)
    nx = c1[:, 0] - c0[:, 0] + 1
    ny = c1[:, 1] - c0[:, 1] + 1
    cnt = nx * ny
    idx = np.repeat(np.arange(len(lo)), cnt)
    k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    cx = c0[idx, 0] + k // ny[idx]
    cy = c0[idx, 1] + k % ny[idx]
    order = np.lexsort((idx, cy, cx))
    cx, cy, idx = cx[order], cy[order], idx[order]
    out = {}
    if len(idx):
        brk = np.nonzero((np.diff(cx) != 0) | (np.diff(cy) != 0))[0] + 1
        for s, e in zip(np.r_[0, brk], np.r_[brk, len(idx)]):
            out[(int(cx[s]), int(cy[s]))] = idx[s:e]
    return out


def _points_by_cell(xy: np.ndarray):
    """``[(cell, point indices)]`` grouping points by the grid cell they lie in."""
    c = _cell_of(xy)
    order = np.lexsort((c[:, 1], c[:, 0]))
    c = c[order]
    if not len(order):
        return []
    brk = np.nonzero((np.diff(c[:, 0]) != 0) | (np.diff(c[:, 1]) != 0))[0] + 1
    return [((int(c[s, 0]), int(c[s, 1])), order[s:e])
            for s, e in zip(np.r_[0, brk], np.r_[brk, len(order)])]


def _probe_uncovered(tris: np.ndarray, pts: np.ndarray, outs: np.ndarray) -> np.ndarray:
    """For each edge point, is its outward probe covered by no region face
    whose plane there is within the step-up of the point?"""
    if len(pts) == 0:
        return np.zeros(0, bool)
    probe = pts[:, :2] + ORACLE_PROBE * outs
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    det = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    good = np.nonzero(np.abs(det) > 1e-12)[0]
    by_cell = _boxes_by_cell(tris[good, :, :2].min(axis=1), tris[good, :, :2].max(axis=1))
    res = np.ones(len(pts), bool)
    for cell, pi in _points_by_cell(probe):
        ti = by_cell.get(cell)
        if ti is None:
            continue
        ti = good[ti]
        A, B, C, D = a[ti], b[ti], c[ti], det[ti]
        for s in range(0, len(pi), 512):
            ii = pi[s:s + 512]
            p = probe[ii, None, :]
            l1 = ((B[:, 1] - C[:, 1]) * (p[..., 0] - C[:, 0])
                  + (C[:, 0] - B[:, 0]) * (p[..., 1] - C[:, 1])) / D
            l2 = ((C[:, 1] - A[:, 1]) * (p[..., 0] - C[:, 0])
                  + (A[:, 0] - C[:, 0]) * (p[..., 1] - C[:, 1])) / D
            l3 = 1.0 - l1 - l2
            inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
            z = l1 * A[:, 2] + l2 * B[:, 2] + l3 * C[:, 2]
            near = np.abs(z - pts[ii, None, 2]) <= ORACLE_STEP_UP + 1e-6
            res[ii] = ~(inside & near).any(axis=1)
    return res


def floor_boundary_samples(ter, region, step: float = 0.5):
    """Sample every Floor_Region edge at the midpoints of ``step``-long pieces.

    Returns ``(points, weights, boundary)``: the (N, 3) sample points, the edge
    length each stands for, and whether it is on the Floor_Boundary by the
    definition. The oracle shared by the fidelity, completeness and
    reachable-only properties.
    """
    tris = _region_tris(ter, region)
    A, B, out = _region_edges(tris)
    L = np.linalg.norm(B - A, axis=1)
    n = np.maximum(1, np.ceil(L / step)).astype(np.int64)
    e = np.repeat(np.arange(len(A)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    t = (k + 0.5) / n[e]
    pts = A[e] + t[:, None] * (B[e] - A[e])
    w = L[e] / n[e]
    return pts, w, _probe_uncovered(tris, pts, out[e])


def on_floor_boundary(ter, region, points, tol: float = 0.05) -> np.ndarray:
    """Is each point within ``tol`` of the Floor_Boundary? Searches the region
    edge points inside the ``tol`` ball (nearest point plus offsets along the
    edge) for one whose outward probe is uncovered."""
    tris = _region_tris(ter, region)
    A, B, out = _region_edges(tris)
    AB = B - A
    L2 = np.einsum("ij,ij->i", AB, AB)
    pts = np.asarray(points, float).reshape(-1, 3)
    res = np.zeros(len(pts), bool)
    offs = np.linspace(-1.0, 1.0, 9)
    by_cell = _boxes_by_cell(np.minimum(A, B)[:, :2] - tol, np.maximum(A, B)[:, :2] + tol)
    owners, cands, couts = [], [], []
    for cell, pi in _points_by_cell(pts[:, :2]):
        ei = by_cell.get(cell)
        if ei is None:
            continue
        q = pts[pi, None, :]                                   # (P, 1, 3)
        t = np.clip(np.einsum("pek,ek->pe", q - A[ei], AB[ei]) / L2[ei], 0.0, 1.0)
        d = np.linalg.norm(A[ei] + t[..., None] * AB[ei] - q, axis=2)
        pp, ee = np.nonzero(d <= tol)
        if not len(pp):
            continue
        e = ei[ee]
        smax = np.sqrt(np.maximum(tol * tol - d[pp, ee] ** 2, 0.0)) / np.sqrt(L2[e])
        tt = np.clip(t[pp, ee, None] + offs[None, :] * smax[:, None], 0.0, 1.0).reshape(-1)
        e = np.repeat(e, len(offs))
        own = np.repeat(pi[pp], len(offs))
        cand = A[e] + tt[:, None] * AB[e]
        ok = np.linalg.norm(cand - pts[own], axis=1) <= tol + 1e-9
        owners.append(own[ok])
        cands.append(cand[ok])
        couts.append(out[e][ok])
    if owners:
        own = np.concatenate(owners)
        unc = _probe_uncovered(tris, np.concatenate(cands), np.concatenate(couts))
        np.logical_or.at(res, own, unc)
    return res


def reference_bands(levels, others=(), max_bands: int = 4):
    """The Property 7 model of depth bands for a stacked world.

    ``levels`` are the heights of flat, mutually XY-overlapping slabs (every
    pair more than 12 u apart counts as stacked); ``others`` are the
    ``(zmin, zmax)`` height ranges of floor that overlaps nothing. Cuts sit
    halfway between consecutive levels more than 12 u apart; while there are
    more than ``max_bands`` bands, the adjacent pair with the smallest gap
    (lowest floor of the upper band minus highest floor of the lower, from
    every height range clipped into the band) merges, ties to the lower pair.
    Returns the level indices per band, bottom to top.
    """
    h = sorted(levels)
    cuts = [(a + b) / 2.0 for a, b in zip(h, h[1:]) if b - a > 12.0]
    bounds = [-math.inf] + cuts + [math.inf]
    slabs = list(zip(bounds[:-1], bounds[1:]))
    ranges = [(z, z) for z in h] + [tuple(r) for r in others]

    def extent(lo, hi):
        inside = [(max(a, lo), min(b, hi)) for a, b in ranges if a < hi and b >= lo]
        return (min(a for a, _ in inside), max(b for _, b in inside))

    ext = [extent(lo, hi) for lo, hi in slabs]
    while len(slabs) > max_bands:
        gaps = [ext[i + 1][0] - ext[i][1] for i in range(len(slabs) - 1)]
        i = gaps.index(min(gaps))
        slabs[i:i + 2] = [(slabs[i][0], slabs[i + 1][1])]
        ext[i:i + 2] = [(min(ext[i][0], ext[i + 1][0]), max(ext[i][1], ext[i + 1][1]))]
    return [[k for k, z in enumerate(levels) if lo <= z < hi] for lo, hi in slabs]


def doorway_spans(spec):
    """Every Doorway_Span of ``spec``, as ``((x0, y0, z), (x1, y1, z))``.

    For each corridor end, from ``routing.corridor_route`` (D1): the segment on
    its room's footprint boundary that the end leg crosses, perpendicular to
    that leg, centred on the leg's axis (the cross coordinate of the leg's
    first waypoint, as the mesh builds it: a near-collinear "straight" route
    keeps that axis to its far end), as long as the corridor is wide, at the
    room's floor height. Its endpoints are the opening's side edges. A span
    is clipped to its wall's extent: where a corridor end overhangs a room
    corner, the part past the corner is not on the room's footprint boundary.
    Only ends whose room is known are returned (a hand-authored corridor
    without rooms has no footprint boundary to cross).
    """
    from generators.routing import corridor_route

    rooms = {r.id: r for r in spec.rooms}
    spans = []
    for cor in spec.corridors:
        route = corridor_route(cor, rooms)
        wps = route.waypoints
        hw = cor.width / 2.0
        for room_id, k, (ex, ey) in ((cor.from_room, 0, wps[0]),
                                     (cor.to_room, len(wps) - 2, wps[-1])):
            room = rooms.get(room_id)
            if room is None:
                continue
            x0, x1 = room.center_x - room.width / 2.0, room.center_x + room.width / 2.0
            y0, y1 = room.center_y - room.depth / 2.0, room.center_y + room.depth / 2.0
            z = room.floor_z
            if route.axes[k]:      # end leg runs along X: an E or W wall
                x = x1 if ex >= room.center_x else x0
                axis = wps[k][1]
                lo, hi = max(axis - hw, y0), min(axis + hw, y1)
                if hi > lo:
                    spans.append(((x, lo, z), (x, hi, z)))
            else:                  # end leg runs along Y: an N or S wall
                y = y1 if ey >= room.center_y else y0
                axis = wps[k][0]
                lo, hi = max(axis - hw, x0), min(axis + hw, x1)
                if hi > lo:
                    spans.append(((lo, y, z), (hi, y, z)))
    return spans
