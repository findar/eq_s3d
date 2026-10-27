"""
analyzer/rof2check.py
---------------------
The RoF2 Format_Checker (Tier-1 format gate).

Given a built ``.eqg`` and the :class:`~generators.zone_spec.ZoneSpec` it was
built from, :func:`check_eqg` runs a fixed set of structural checks and returns
a :class:`FormatReport`. The pipeline gate (task 20.3) merges
``report.to_dict()`` into the ``.zone.json`` Sidecar and rejects a build whose
report does not pass.

Design contract (`.kiro/specs/zone-generator-m1-controls-traversability`,
"#### Format_Checker", Req 9.1 / 9.3 / 9.4):

* **The checker is TOTAL.** It NEVER raises. Every structural fault — a corrupt
  archive, a TER that will not parse, a bad material index — becomes a FAILED
  :class:`FormatCheck` carrying a human-readable message that names the check,
  not an exception that crashes the gate. Each check function is wrapped in
  ``try/except Exception`` by the driver; an escaping exception becomes
  ``FormatCheck(name, False, [f"{name}: raised {type(e).__name__}: {e}"])``.
* **Every check is always present.** A corrupt archive yields a report with one
  entry per check name, the root cause named on the check that owns it, and the
  checks that DEPEND on that unreadable input marked "skipped" (still failing)
  while INDEPENDENT checks still run. So the report is a complete, specific
  diagnosis — never a single bare crash. (This is what Property 14 asserts.)
* **No ``normals_resolve`` check.** The umbrella "RoF2 format check" had one;
  M1 drops it deliberately (Req 9.4). The hygiene test (task 20.8) asserts its
  absence, so do NOT add it back.

The eleven checks, in order, with the input each depends on::

    pfs_reads         archive bytes            (independent — always runs)
    required_files    pfs_reads entries
    ter_roundtrip     the ter_<name>.ter entry
    zon_roundtrip     the <name>.zon entry
    zon_model_ref     ZON parse
    material_indices  TER parse
    diffuse_textures  TER parse + entries
    collision_policy  TER parse
    safe_point        TER parse
    bounds_sane       TER parse
    name_consistent   entries + ZON + Sidecar

``passed = all(c.passed for c in checks)`` (Req 9.1). ``name_consistent`` is the
build half of umbrella Req 9.7 only — M1 has no Known_Zone_List membership
check (that is the Export half, M6).
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.pfs import RawEntry, read_directory
from core.ter import FLAG_PASSABLE, PROP_DIFFUSE, PROP_TYPE_STRING, TerFile
from core.zon import ZonFile
from generators.zone_spec import ZoneSpec

# AgentModel is only needed for its slope cap default; import lazily to keep the
# dependency surface small (analyzer.traverse pulls in numpy + routing).
from analyzer.traverse import AgentModel


# ---------------------------------------------------------------------------
# Tunable constants (design "Constants", `analyzer/rof2check.py`)
# ---------------------------------------------------------------------------

#: Material-name prefixes that MAY carry a passable (non-collidable) polygon —
#: liquid surfaces a player swims through. None are emitted in M1, so in M1
#: every polygon must be collidable; the prefix list keeps ``collision_policy``
#: honest for when liquids land.
LIQUID_SURFACE_PREFIXES: Tuple[str, ...] = ("liquid_",)

#: ``bounds_sane`` rejects any vertex coordinate whose magnitude reaches this.
MAX_COORD: float = 30000.0

#: ``safe_point`` tolerances: a standable face must come within ``SAFE_POINT_XY``
#: units of the spec safe point in XY, and its plane Z at the closest point must
#: lie in ``[safe_z - SAFE_POINT_DZ, safe_z]`` (on or just above the floor).
SAFE_POINT_XY: float = 50.0
SAFE_POINT_DZ: float = 10.0


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------

@dataclass
class FormatCheck:
    """One check's result.

    ``name`` is the stable check id (e.g. ``"ter_roundtrip"``). ``passed`` is the
    verdict. ``messages`` carries zero or more human-readable lines; by
    convention every line STARTS with ``"<name>: "`` so a reader (and Property
    14) can attribute it to this check. A passing check usually has no messages.

    A check whose input could not be read reports ``skipped=True`` AND
    ``passed=False`` — it did not run, so it cannot vouch for the archive, but it
    is distinguished from a check that ran and found a real fault. ``passed``
    (not ``skipped``) is what the gate reads.
    """

    name: str
    passed: bool
    messages: List[str] = field(default_factory=list)
    skipped: bool = False

    def to_dict(self) -> dict:
        d = {"name": self.name, "passed": self.passed, "messages": list(self.messages)}
        if self.skipped:
            d["skipped"] = True
        return d


@dataclass
class FormatReport:
    """The whole Format_Checker verdict: one :class:`FormatCheck` per check.

    ``passed`` is ``all(c.passed for c in checks)`` (Req 9.1) — a skipped check
    fails the report, because a build whose TER could not even be parsed has not
    earned a pass. ``messages`` flattens every check's messages; ``failed_checks``
    names the checks the gate (task 20.3) records in its failure log;
    ``to_dict()`` is the shape merged into the Sidecar.
    """

    passed: bool
    checks: List[FormatCheck]

    @property
    def messages(self) -> List[str]:
        out: List[str] = []
        for c in self.checks:
            out.extend(c.messages)
        return out

    @property
    def failed_checks(self) -> List[str]:
        """Names of the checks that did not pass (failed or skipped)."""
        return [c.name for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        # {"passed", "checks": [{"name", "passed", "messages"[, "skipped"]}]}
        return {"passed": self.passed, "checks": [c.to_dict() for c in self.checks]}


# ---------------------------------------------------------------------------
# The ordered list of check names (single source of truth; no normals_resolve)
# ---------------------------------------------------------------------------

CHECK_NAMES: Tuple[str, ...] = (
    "pfs_reads",
    "required_files",
    "ter_roundtrip",
    "zon_roundtrip",
    "zon_model_ref",
    "material_indices",
    "diffuse_textures",
    "collision_policy",
    "safe_point",
    "bounds_sane",
    "name_consistent",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _ok(name: str, messages: Optional[List[str]] = None) -> FormatCheck:
    return FormatCheck(name=name, passed=True, messages=messages or [])


def _fail(name: str, message: str) -> FormatCheck:
    return FormatCheck(name=name, passed=False, messages=[f"{name}: {message}"])


def _skip(name: str, dependency: str) -> FormatCheck:
    """A dependent check whose input could not be read (Req 9.3)."""
    return FormatCheck(
        name=name,
        passed=False,
        messages=[f"{name}: skipped, {dependency} unreadable"],
        skipped=True,
    )


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _entry_by_name(entries: List[RawEntry], name: str) -> Optional[RawEntry]:
    """Case-insensitive lookup of a named entry whose data was recovered."""
    target = name.lower()
    for e in entries:
        if e.name is not None and e.name.lower() == target:
            return e
    return None


def _winding_normal_z(a, b, c) -> Tuple[float, float]:
    """Return ``(nz, length)`` of the un-normalised face normal's Z component.

    Uses the same winding convention as :mod:`analyzer.traverse`:
    ``n = (v1->v2) x (v1->v3)``. ``length`` is the normal's magnitude; a
    degenerate (zero-area) triangle has ``length == 0``.
    """
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return nz, length


def _point_seg_dist_xy(px, py, ax, ay, bx, by) -> float:
    """Distance in XY from point P to segment AB."""
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 <= 1e-18:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _point_in_tri_xy(px, py, tri) -> bool:
    ax, ay = tri[0][0], tri[0][1]
    bx, by = tri[1][0], tri[1][1]
    cx, cy = tri[2][0], tri[2][1]
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(det) < 1e-12:
        return False
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    l3 = 1.0 - l1 - l2
    return l1 >= -1e-9 and l2 >= -1e-9 and l3 >= -1e-9


def _tri_xy_dist_to_point(px, py, tri) -> float:
    """XY distance from ``(px, py)`` to a triangle's XY footprint (0 inside)."""
    if _point_in_tri_xy(px, py, tri):
        return 0.0
    return min(
        _point_seg_dist_xy(px, py, tri[0][0], tri[0][1], tri[1][0], tri[1][1]),
        _point_seg_dist_xy(px, py, tri[1][0], tri[1][1], tri[2][0], tri[2][1]),
        _point_seg_dist_xy(px, py, tri[2][0], tri[2][1], tri[0][0], tri[0][1]),
    )


def _plane_z_at(px, py, tri) -> Optional[float]:
    """Z of the triangle's plane at ``(px, py)`` (None if the plane is vertical)."""
    a, b, c = tri
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    if abs(nz) < 1e-12:
        return None
    # Plane: nx*(x-ax) + ny*(y-ay) + nz*(z-az) = 0
    return a[2] - (nx * (px - a[0]) + ny * (py - a[1])) / nz


# ---------------------------------------------------------------------------
# Individual checks. Each returns ONE FormatCheck and may raise; the driver
# wraps every call so a raise becomes a named failed check.
# ---------------------------------------------------------------------------

def _check_pfs_reads(data: bytes, entries: List[RawEntry],
                     archive_errors: List[str]) -> FormatCheck:
    """Header valid; every entry inflated to its recorded size; every name block
    name has an entry. Independent — always runs (uses the non-raising
    ``read_directory`` so a malformed archive is a failed check, not a crash)."""
    name = "pfs_reads"
    messages: List[str] = []
    for err in archive_errors:
        messages.append(f"{name}: archive unreadable: {err}")
    if archive_errors:
        return FormatCheck(name=name, passed=False, messages=messages)

    if not entries:
        return _fail(name, "no directory entries recovered")

    for e in entries:
        if e.error is not None:
            label = e.name if e.name is not None else f"crc 0x{e.crc:08x}"
            messages.append(f"{name}: entry {label}: {e.error}")

    if messages:
        return FormatCheck(name=name, passed=False, messages=messages)
    return _ok(name)


def _check_required_files(entries: List[RawEntry], ter_name: str,
                          zon_name: str) -> FormatCheck:
    name = "required_files"
    present = {e.name.lower() for e in entries if e.name is not None}
    missing = [n for n in (ter_name, zon_name) if n.lower() not in present]
    if missing:
        return _fail(name, f"missing entries: {', '.join(missing)}")
    return _ok(name)


def _check_roundtrip(name: str, raw: bytes, parse: Callable[[bytes], object],
                     entry_label: str) -> FormatCheck:
    """``parse(raw).to_bytes() == raw`` for the named entry."""
    obj = parse(raw)
    out = obj.to_bytes()
    if out != raw:
        return _fail(
            name,
            f"{entry_label} does not round-trip: re-serialised {len(out)} bytes "
            f"!= original {len(raw)} bytes",
        )
    return _ok(name)


def _check_zon_model_ref(zon: ZonFile, expected: str) -> FormatCheck:
    name = "zon_model_ref"
    if not zon.models:
        return _fail(name, "ZON has no models")
    got = zon.models[0]
    if got != expected:
        return _fail(name, f"models[0] is {got!r}, expected {expected!r}")
    return _ok(name)


def _check_material_indices(ter: TerFile) -> FormatCheck:
    name = "material_indices"
    n = len(ter.materials)
    for i, p in enumerate(ter.polygons):
        if p.material < 0 or p.material >= n:
            return _fail(
                name,
                f"polygon {i} material index {p.material} out of range [0, {n})",
            )
    return _ok(name)


def _check_diffuse_textures(ter: TerFile, entries: List[RawEntry]) -> FormatCheck:
    name = "diffuse_textures"
    for mat in ter.materials:
        diffuse = None
        for prop in mat.properties:
            if prop.name == PROP_DIFFUSE and prop.type == PROP_TYPE_STRING:
                diffuse = prop.value_s
                break
        if not diffuse:
            return _fail(
                name,
                f"material {mat.index} {mat.name!r} has no {PROP_DIFFUSE}",
            )
        entry = _entry_by_name(entries, diffuse)
        if entry is None or entry.data is None:
            return _fail(
                name,
                f"material {mat.index} {mat.name!r} → {diffuse!r} is not packed",
            )
        dds = entry.data
        if len(dds) < 128 or dds[:4] != b"DDS ":
            return _fail(
                name,
                f"material {mat.index} {mat.name!r} → {diffuse!r} is not a DDS file",
            )
        # Layout: [0..4) 'DDS ' magic, then the 124-byte DDS_HEADER:
        #   header+0  = dwSize (124)  → file offset 4
        #   header+8  = dwHeight      → file offset 12
        #   header+12 = dwWidth       → file offset 16
        (hsize,) = struct.unpack_from("<I", dds, 4)
        (height,) = struct.unpack_from("<I", dds, 12)
        (width,) = struct.unpack_from("<I", dds, 16)
        if hsize != 124:
            return _fail(
                name,
                f"material {mat.index} {mat.name!r} → {diffuse!r} DDS header size "
                f"{hsize} (expected 124)",
            )
        if not (_is_power_of_two(width) and _is_power_of_two(height)):
            return _fail(
                name,
                f"material {mat.index} {mat.name!r} → {diffuse!r} is {width}×{height} "
                f"(not a power of two)",
            )
    return _ok(name)


def _check_collision_policy(ter: TerFile) -> FormatCheck:
    name = "collision_policy"
    collidable = 0
    for i, p in enumerate(ter.polygons):
        passable = bool(p.flags & FLAG_PASSABLE)
        if passable:
            mat_name = ""
            if 0 <= p.material < len(ter.materials):
                mat_name = ter.materials[p.material].name.lower()
            allowed = any(mat_name.startswith(pre) for pre in LIQUID_SURFACE_PREFIXES)
            if not allowed:
                return _fail(
                    name,
                    f"polygon {i} is passable but material {p.material} "
                    f"{mat_name!r} is not a liquid surface",
                )
        else:
            collidable += 1
    if collidable == 0:
        return _fail(name, "no collidable polygons")
    return _ok(name)


def _check_safe_point(ter: TerFile, spec: ZoneSpec, agent: AgentModel) -> FormatCheck:
    name = "safe_point"
    sx, sy, sz = spec.safe_point
    min_up = agent.min_up_normal
    verts = ter.vertices
    best_dist = None
    for p in ter.polygons:
        a = verts[p.v1]
        b = verts[p.v2]
        c = verts[p.v3]
        tri = ((a.x, a.y, a.z), (b.x, b.y, b.z), (c.x, c.y, c.z))
        nz, length = _winding_normal_z(*tri)
        if length <= 0.0:
            continue
        # Standable: |nz| / |n| >= cos(slope). Either winding of an up-ish face.
        if abs(nz) / length < min_up:
            continue
        dist = _tri_xy_dist_to_point(sx, sy, tri)
        if dist > SAFE_POINT_XY:
            continue
        # Z of the standable plane at the closest XY point to the safe point.
        if _point_in_tri_xy(sx, sy, tri):
            px, py = sx, sy
        else:
            px, py = _closest_xy_on_tri(sx, sy, tri)
        pz = _plane_z_at(px, py, tri)
        if pz is None:
            continue
        if (sz - SAFE_POINT_DZ) <= pz <= sz:
            return _ok(name)
        best_dist = dist if best_dist is None else min(best_dist, dist)
    if best_dist is None:
        return _fail(
            name,
            f"no standable floor within {SAFE_POINT_XY:g}u of safe point "
            f"({sx:g}, {sy:g}, {sz:g})",
        )
    return _fail(
        name,
        f"standable floor near safe point ({sx:g}, {sy:g}, {sz:g}) but its Z is "
        f"outside [{sz - SAFE_POINT_DZ:g}, {sz:g}]",
    )


def _closest_xy_on_tri(px, py, tri) -> Tuple[float, float]:
    """Closest point in XY on a triangle's footprint (edges only; inside handled
    by the caller)."""
    best = None
    best_d = None
    edges = ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0]))
    for (a, b) in edges:
        dx, dy = b[0] - a[0], b[1] - a[1]
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-18:
            cx, cy = a[0], a[1]
        else:
            t = ((px - a[0]) * dx + (py - a[1]) * dy) / seg2
            t = max(0.0, min(1.0, t))
            cx, cy = a[0] + t * dx, a[1] + t * dy
        d = math.hypot(px - cx, py - cy)
        if best_d is None or d < best_d:
            best_d, best = d, (cx, cy)
    return best


def _check_bounds_sane(ter: TerFile) -> FormatCheck:
    name = "bounds_sane"
    for i, v in enumerate(ter.vertices):
        for axis, c in (("x", v.x), ("y", v.y), ("z", v.z)):
            if not math.isfinite(c):
                return _fail(name, f"vertex {i} {axis}={c} is not finite")
            if abs(c) >= MAX_COORD:
                return _fail(
                    name,
                    f"vertex {i} {axis}={c:g} exceeds |{MAX_COORD:g}|",
                )
    if not ter.vertices:
        return _fail(name, "TER has no vertices")
    return _ok(name)


def _check_name_consistent(spec: ZoneSpec, entries: List[RawEntry],
                           archive_stem: str, ter_name: str, zon_name: str,
                           zon: Optional[ZonFile],
                           sidecar_name: Optional[str]) -> FormatCheck:
    name = "name_consistent"
    build = spec.name.lower()
    problems: List[str] = []

    if archive_stem.lower() != build:
        problems.append(f"archive stem {archive_stem!r} != {build!r}")

    present = {e.name.lower() for e in entries if e.name is not None}
    if ter_name.lower() not in present:
        problems.append(f"TER entry {ter_name!r} missing")
    if zon_name.lower() not in present:
        problems.append(f"ZON entry {zon_name!r} missing")

    expected_ref = f"TER_{build.upper()}.TER"
    if zon is not None:
        if not zon.models:
            problems.append("ZON model ref missing")
        elif zon.models[0] != expected_ref:
            problems.append(f"ZON model ref {zon.models[0]!r} != {expected_ref!r}")

    if sidecar_name is not None and sidecar_name.lower() != build:
        problems.append(f"Sidecar name {sidecar_name!r} != {build!r}")

    if problems:
        return _fail(name, "; ".join(problems))
    return _ok(name)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _wrap(name: str, fn: Callable[[], FormatCheck]) -> FormatCheck:
    """Run ``fn`` so any exception becomes a named failed check (Req 9.3)."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — totality is the point
        return FormatCheck(
            name=name,
            passed=False,
            messages=[f"{name}: raised {type(e).__name__}: {e}"],
        )


def check_eqg(eqg_path: Path, spec: ZoneSpec, *,
              sidecar_path: Optional[Path] = None,
              agent: Optional[AgentModel] = None) -> FormatReport:
    """Run the eleven RoF2 format checks on a built ``.eqg``.

    NEVER raises. Returns a :class:`FormatReport` with one :class:`FormatCheck`
    per name in :data:`CHECK_NAMES`, in that order. A check whose input could not
    be read is marked skipped (and fails); independent checks still run. See the
    module docstring for the dependency graph.

    Parameters
    ----------
    eqg_path:
        Path to the built archive.
    spec:
        The :class:`ZoneSpec` the archive was built from — supplies the
        Build_Name (``spec.name``) and the safe point.
    sidecar_path:
        Optional path to the ``.zone.json`` Sidecar; when given, its ``name`` is
        compared in ``name_consistent``.
    agent:
        Optional :class:`AgentModel` (slope cap for ``safe_point``); a default is
        used when omitted.
    """
    agent = agent or AgentModel()
    eqg_path = Path(eqg_path)
    build = spec.name.lower()
    ter_name = f"ter_{build}.ter"
    zon_name = f"{build}.zon"
    archive_stem = eqg_path.stem

    checks: List[FormatCheck] = []

    # --- Read the archive once, non-raising -------------------------------
    data = b""
    try:
        data = eqg_path.read_bytes()
    except Exception as e:  # noqa: BLE001
        # The whole archive is unreadable: pfs_reads fails with the reason and
        # every dependent skips. Build a report directly.
        reason = f"could not read {eqg_path.name}: {type(e).__name__}: {e}"
        pfs = FormatCheck("pfs_reads", False, [f"pfs_reads: {reason}"])
        checks.append(pfs)
        for n in CHECK_NAMES[1:]:
            checks.append(_skip(n, "pfs_reads"))
        return FormatReport(passed=False, checks=checks)

    entries: List[RawEntry] = []
    archive_errors: List[str] = []
    try:
        entries, archive_errors = read_directory(data)
    except Exception as e:  # noqa: BLE001 — read_directory is non-raising, belt+braces
        archive_errors = [f"directory read raised {type(e).__name__}: {e}"]

    # --- pfs_reads (independent) ------------------------------------------
    pfs_check = _wrap(
        "pfs_reads",
        lambda: _check_pfs_reads(data, entries, archive_errors),
    )
    checks.append(pfs_check)
    archive_readable = pfs_check.passed

    # --- Locate the TER/ZON entries and parse them (best effort) ----------
    ter_entry = _entry_by_name(entries, ter_name)
    zon_entry = _entry_by_name(entries, zon_name)

    ter_obj: Optional[TerFile] = None
    ter_parse_error: Optional[str] = None
    if ter_entry is not None and ter_entry.data is not None:
        try:
            ter_obj = TerFile.from_bytes(ter_entry.data, name=build)
        except Exception as e:  # noqa: BLE001
            ter_parse_error = f"{type(e).__name__}: {e}"

    zon_obj: Optional[ZonFile] = None
    if zon_entry is not None and zon_entry.data is not None:
        try:
            zon_obj = ZonFile.from_bytes(zon_entry.data)
        except Exception as e:  # noqa: BLE001
            zon_obj = None

    # --- required_files (depends on pfs_reads entries) --------------------
    checks.append(
        _wrap("required_files",
              lambda: _check_required_files(entries, ter_name, zon_name))
    )

    # --- ter_roundtrip (depends on the TER entry) -------------------------
    if ter_entry is None or ter_entry.data is None:
        checks.append(_skip("ter_roundtrip", f"entry {ter_name}"))
    else:
        checks.append(
            _wrap("ter_roundtrip",
                  lambda: _check_roundtrip(
                      "ter_roundtrip", ter_entry.data,
                      lambda b: TerFile.from_bytes(b, name=build), ter_name))
        )

    # --- zon_roundtrip (depends on the ZON entry) -------------------------
    if zon_entry is None or zon_entry.data is None:
        checks.append(_skip("zon_roundtrip", f"entry {zon_name}"))
    else:
        checks.append(
            _wrap("zon_roundtrip",
                  lambda: _check_roundtrip(
                      "zon_roundtrip", zon_entry.data, ZonFile.from_bytes, zon_name))
        )

    # --- zon_model_ref (depends on ZON parse) -----------------------------
    expected_ref = f"TER_{build.upper()}.TER"
    if zon_obj is None:
        checks.append(_skip("zon_model_ref", f"ZON {zon_name}"))
    else:
        checks.append(
            _wrap("zon_model_ref",
                  lambda: _check_zon_model_ref(zon_obj, expected_ref))
        )

    # --- The TER-derived checks (depend on TER parse) ---------------------
    ter_dep = f"TER {ter_name}" if ter_parse_error is None else f"TER {ter_name} ({ter_parse_error})"
    for cname, cfn in (
        ("material_indices", lambda: _check_material_indices(ter_obj)),
        ("diffuse_textures", lambda: _check_diffuse_textures(ter_obj, entries)),
        ("collision_policy", lambda: _check_collision_policy(ter_obj)),
        ("safe_point", lambda: _check_safe_point(ter_obj, spec, agent)),
        ("bounds_sane", lambda: _check_bounds_sane(ter_obj)),
    ):
        if ter_obj is None:
            checks.append(_skip(cname, ter_dep))
        else:
            checks.append(_wrap(cname, cfn))

    # --- name_consistent (entries + ZON + Sidecar) ------------------------
    sidecar_name: Optional[str] = None
    if sidecar_path is not None:
        try:
            sp = Path(sidecar_path)
            if sp.exists():
                sidecar_name = json.loads(sp.read_text()).get("name")
        except Exception:  # noqa: BLE001 — a bad Sidecar is a name_consistent fail, caught below
            sidecar_name = None
    if not archive_readable:
        # The directory could not be read: names cannot be compared.
        checks.append(_skip("name_consistent", "pfs_reads"))
    else:
        checks.append(
            _wrap("name_consistent",
                  lambda: _check_name_consistent(
                      spec, entries, archive_stem, ter_name, zon_name,
                      zon_obj, sidecar_name))
        )

    # Keep the canonical order (checks were appended in order, but be explicit).
    by_name = {c.name: c for c in checks}
    ordered = [by_name[n] for n in CHECK_NAMES]
    passed = all(c.passed for c in ordered)
    return FormatReport(passed=passed, checks=ordered)
