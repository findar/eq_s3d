"""
generators/export.py
--------------------
The Export (umbrella Requirement 8.10-8.12, step 17 Requirement 2): a copy of an
accepted build named for an existing RoF2 zone short name it takes over
(default ``arena``), written beside the build in ``<build dir>/export/<short>/``.

An Export renames, it never rebuilds:

* ``<short>.eqg``: every entry of ``<name>.eqg``, with ``ter_<name>.ter`` and
  ``<name>.zon`` renamed to ``ter_<short>.ter`` and ``<short>.zon`` and the ZON's
  first model reference set to ``TER_<SHORT>.TER``. Every other entry (textures,
  placed and unplaced ``.mod`` files, whatever the build packed) is carried
  through byte for byte under its own name. ``PfsArchive`` computes each CRC
  from the entry's name when it writes, so the renamed entries get EQ's CRC for
  their new names (lessons-learned "PFS CRC").
* ``maps/<short>.txt`` ... ``maps/<short>_3.txt``: the build's map files, same
  bytes, new names.
* ``<short>.zone.json``: the build's sidecar plus ``shortname`` and the
  Export's options (``export``).

The exported archive then goes through the Format_Checker with the short name as
the expected name (``check_eqg(..., expected_name=short)``). The build's own
files are only read; nothing outside ``<build dir>/export/<short>/`` is written,
and writing the same Export again replaces that folder.

When the format check passes, :func:`_after_check` (the one place that runs only
then) adds ``<short>.sql`` (``sqlexport.export_sql``) and ``INSTALL.txt`` and sets
``ExportResult.sql_written``. :func:`write_bundle` zips the export into
``<short>.bundle.zip`` in the same folder, on request (the route and the CLI).
"""

from __future__ import annotations

import io
import json
import math
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from analyzer.rof2check import FormatReport, check_eqg
from analyzer.zonelist import DEFAULT_TARGET, closest, is_known
from core.paths import OutputRoot
from core.pfs import PfsArchive
from core.zon import ZonFile
from generators.doors import DOOR_MODEL, DOOR_WIDTH
from generators.sqlexport import SqlExportError, export_sql
from generators.zone_spec import ZoneSpec

#: The sub-folder of a build directory that holds its Exports.
EXPORT_DIR = "export"

#: The install notes in every export folder and bundle.
INSTALL_FILE = "INSTALL.txt"

#: Stock files a takeover moves aside in the client folder (archive.md decision 7);
#: ``{s}`` is the short name. ``<short>_chr.*`` (the zone's NPC models) stays.
MOVE_ASIDE = ("{s}.eqg", "{s}.zon", "{s}.s3d", "{s}_obj.s3d", "{s}_EnvironmentEmitters.txt")

#: One time stamp for every bundle entry, so a bundle's bytes depend on its files alone.
_ZIP_TIME = (1999, 3, 16, 0, 0, 0)

_MAP_FILE = r"(_[0-9]+)?\.txt"


class ExportError(Exception):
    """The build can't be exported (a file it needs is missing or unreadable)."""


class UnknownShortname(ExportError, ValueError):
    """The Target_Shortname is not on the Known_Zone_List (umbrella 8.8).

    ``shortname`` is the name as given; ``close`` holds up to 5 known names
    closest to it. The message names both."""

    def __init__(self, shortname: str, close: List[str]):
        self.shortname = shortname
        self.close = list(close)
        hint = f"; closest: {', '.join(self.close)}" if self.close else ""
        super().__init__(f"unknown short name {shortname!r}{hint}")


@dataclass
class ExportResult:
    shortname: str                    # lower case, e.g. "arena"
    dir: Path                         # <build dir>/export/<short>
    files: List[Path] = field(default_factory=list)   # every file written, archive first
    format: Optional[FormatReport] = None
    sql_written: bool = False         # <short>.sql was written (the format check passed)
    warnings: List[str] = field(default_factory=list)
    clear_spawns: bool = False        # the SQL also deletes the zone's spawns

    @property
    def eqg_path(self) -> Path:
        return self.dir / f"{self.shortname}.eqg"

    @property
    def sidecar_path(self) -> Path:
        return self.dir / f"{self.shortname}.zone.json"

    @property
    def sql_path(self) -> Path:
        return self.dir / f"{self.shortname}.sql"

    @property
    def bundle_path(self) -> Path:
        return self.dir / bundle_name(self.shortname)


def bundle_name(short: str) -> str:
    """The bundle's file name in the export folder."""
    return f"{short}.bundle.zip"


def resolve_shortname(shortname: Optional[str]) -> str:
    """The Target_Shortname to use: blank is the Default_Target (8.7), any case
    matches (8.14), and a name off the Known_Zone_List raises
    :class:`UnknownShortname` (8.8)."""
    short = (shortname or "").strip().lower()
    if not short:
        return DEFAULT_TARGET
    if not is_known(short):
        raise UnknownShortname(shortname.strip(), closest(short))
    return short


def build_name(build_dir: Path) -> str:
    """The Build_Name of a build directory: the stem of its one ``.eqg``."""
    eqgs = sorted(p for p in Path(build_dir).glob("*.eqg") if p.is_file())
    if len(eqgs) != 1:
        raise ExportError(f"expected one .eqg in {Path(build_dir).name}, found {len(eqgs)}")
    return eqgs[0].stem.lower()


def _load_spec(build_dir: Path, name: str) -> ZoneSpec:
    path = Path(build_dir) / f"{name}.spec.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc.pop("decor_layers", None)
        return ZoneSpec.from_dict(doc)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ExportError(f"{path.name}: {type(exc).__name__}") from None


def export_archive(src: PfsArchive, name: str, short: str) -> PfsArchive:
    """The exported archive: ``src``'s entries with the TER and ZON renamed for
    ``short`` and the ZON's first model set to ``TER_<SHORT>.TER``; every other
    entry carried through unchanged."""
    ter_old, zon_old = f"ter_{name}.ter", f"{name}.zon"
    out = PfsArchive()
    seen = set()
    for f in src.files:
        low = f.name.lower()
        if low == ter_old:
            out.add(f"ter_{short}.ter", f.data)
            seen.add(ter_old)
        elif low == zon_old:
            zon = ZonFile.from_bytes(f.data)
            if not zon.models:
                raise ExportError(f"{f.name} has no models")
            zon.models[0] = f"TER_{short.upper()}.TER"
            out.add(f"{short}.zon", zon.to_bytes())
            seen.add(zon_old)
        else:
            out.add(f.name, f.data)
    missing = [n for n in (ter_old, zon_old) if n not in seen]
    if missing:
        raise ExportError(f"{name}.eqg lacks {', '.join(missing)}")
    return out


def _export_sidecar(build_dir: Path, name: str, short: str, map_names: dict,
                    clear_spawns: bool) -> dict:
    """The build's sidecar plus ``shortname`` and the Export's options; its map
    file names point at the exported copies."""
    path = Path(build_dir) / f"{name}.zone.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExportError(f"{path.name}: {type(exc).__name__}") from None
    if not isinstance(doc, dict):
        raise ExportError(f"{path.name}: not an object")
    if isinstance(doc.get("map_files"), list):
        doc["map_files"] = [map_names.get(p, p) for p in doc["map_files"]]
    outline = doc.get("outline")
    if isinstance(outline, dict):
        for band in outline.get("bands") or ():
            if isinstance(band, dict) and band.get("file") in map_names:
                band["file"] = map_names[band["file"]]
    doc["shortname"] = short
    doc["export"] = {"shortname": short, "build": name, "clear_spawns": bool(clear_spawns)}
    return doc


def bounds_min_z(sidecar_path: Path, spec: ZoneSpec) -> float:
    """The build's lowest Z: the sidecar's ``bounds.min`` when it has one, else the
    lowest room floor of the spec (0 for a spec with no rooms)."""
    try:
        doc = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
        z = float(doc["bounds"]["min"][2])
        if math.isfinite(z):
            return z
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    return min((r.bounds[0][2] for r in spec.rooms), default=0.0)


def install_text(short: str) -> str:
    """``INSTALL.txt``: how to put an Export of ``short`` into a client and onto a
    server (CRLF, ASCII). Decision 7 (archive.md) names the stock files to move aside."""
    aside = [m.format(s=short) for m in MOVE_ASIDE]
    lines = [
        f"eq_s3d export: a takeover of the existing zone '{short}'",
        "",
        f"This bundle replaces the zone '{short}' in a RoF2 client and on an EQEmu",
        "server. Nothing in it has been copied into a client or run against a",
        "database: every step below is yours.",
        "",
        "Files",
        f"  {short}.eqg          the zone: terrain, models, textures, its .zon inside",
        f"  maps\\{short}*.txt    the in-game map layers",
        f"  {short}.sql          the server rows: safe point, underworld, doors",
        f"  {short}.zone.json    the build's notes: rooms, gates, advisory data",
        "",
        "1. Client. Work on a COPY of your RoF2 folder, never your only install.",
        "   In the copy, move these stock files out of the folder (keep them to",
        "   put the zone back; skip any that aren't there):",
        *[f"     {a}" for a in aside],
        f"   Keep {short}_chr.s3d and {short}_chr.txt: they hold the zone's NPC",
        "   models, not its geometry.",
        f"   Then copy {short}.eqg into the folder, and maps\\{short}*.txt into its",
        "   maps folder.",
        "",
        "2. Server. Back up the rows the script changes first; its header names",
        f"   them (the zone row and doors rows of '{short}', and its spawn rows when",
        "   the export clears spawns). Read the script, replace the placeholder",
        "   key item ids it names, then apply it by hand, for example:",
        f"     mysql -u <user> -p <database> < {short}.sql",
        "",
        f"3. Check. Zone into '{short}' and look for \"Loaded {short}.EQG.\" in the",
        "   client's Logs\\dbg.txt.",
        "",
        "To undo: move the stock files back into the client folder and restore",
        "the server rows from your backup.",
        "",
    ]
    return "\r\n".join(lines)


def _after_check(result: ExportResult, spec: ZoneSpec, root: OutputRoot) -> None:
    """Runs only when the exported archive passed the Format_Checker (Req 2.2):
    writes ``<short>.sql`` and ``INSTALL.txt`` and sets ``result.sql_written``.
    A spec the SQL can't express leaves no script and a ``sql: ...`` warning."""
    short = result.shortname
    try:
        sql = export_sql(spec, short, bounds_min_z=bounds_min_z(result.sidecar_path, spec),
                         door_model=DOOR_MODEL, door_width=DOOR_WIDTH,
                         clear_spawns=result.clear_spawns)
    except SqlExportError as exc:
        result.warnings.append(f"sql: {exc}")
        return
    for rel, data in ((f"{short}.sql", sql.encode("utf-8")),
                      (INSTALL_FILE, install_text(short).encode("ascii"))):
        result.files.append(root.write_bytes(f"{EXPORT_DIR}/{short}/{rel}", data))
    result.sql_written = True


def bundle_files(export_dir: Path, short: str) -> List[str]:
    """What a bundle of the export in ``export_dir`` holds, relative to it: the
    archive, the maps, the SQL, the sidecar and ``INSTALL.txt``. Raises
    :class:`ExportError` naming any part missing (no SQL: the format check failed)."""
    export_dir = Path(export_dir)
    maps_dir = export_dir / "maps"
    maps = sorted(f"maps/{p.name}" for p in maps_dir.glob("*.txt")) if maps_dir.is_dir() else []
    rels = [f"{short}.eqg", *maps, f"{short}.sql", f"{short}.zone.json", INSTALL_FILE]
    missing = [r for r in rels if not (export_dir / r).is_file()]
    if missing:
        raise ExportError(f"export {short} lacks {', '.join(missing)}")
    return rels


def write_bundle(build_dir: Path, short: str) -> Path:
    """Zip the build's Export of ``short`` into ``export/<short>/<short>.bundle.zip``
    and return its path. Only that file is written."""
    root = OutputRoot(Path(build_dir))
    export_dir = root.path(EXPORT_DIR, short)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for rel in bundle_files(export_dir, short):
            info = zipfile.ZipInfo(rel, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (export_dir / rel).read_bytes())
    return root.write_bytes(f"{EXPORT_DIR}/{short}/{bundle_name(short)}", buf.getvalue())


def export_build(build_dir: Path, shortname: Optional[str] = None, *,
                 clear_spawns: bool = False) -> ExportResult:
    """Export the build in ``build_dir`` as ``shortname`` (default ``arena``).

    Raises :class:`UnknownShortname` for a name off the Known_Zone_List (before
    anything is written) and :class:`ExportError` when the build lacks a file the
    Export reads. A Format_Checker failure does not raise: the archive and files
    are written, ``result.format`` names the failure, and no SQL is written.
    """
    short = resolve_shortname(shortname)
    build_dir = Path(build_dir)
    name = build_name(build_dir)
    spec = _load_spec(build_dir, name)
    try:
        src = PfsArchive.from_file(build_dir / f"{name}.eqg")
    except (OSError, ValueError) as exc:
        raise ExportError(f"{name}.eqg: {type(exc).__name__}: {exc}") from None
    archive = export_archive(src, name, short)

    maps = {}
    maps_dir = build_dir / "maps"
    if maps_dir.is_dir():
        pattern = re.compile(re.escape(name) + _MAP_FILE)
        for p in sorted(maps_dir.iterdir()):
            m = pattern.fullmatch(p.name.lower()) if p.is_file() else None
            if m:
                maps[f"maps/{p.name}"] = (f"maps/{short}{m.group(1) or ''}.txt", p.read_bytes())
    map_names = {old: new for old, (new, _) in maps.items()}
    sidecar = _export_sidecar(build_dir, name, short, map_names, clear_spawns)

    root = OutputRoot(build_dir)
    out_dir = root.path(EXPORT_DIR, short)
    root.remove_tree(out_dir)            # a repeat Export replaces its folder
    root.mkdir(EXPORT_DIR, short)
    result = ExportResult(shortname=short, dir=out_dir, clear_spawns=bool(clear_spawns))

    def write(rel: str, data: bytes) -> None:
        result.files.append(root.write_bytes(f"{EXPORT_DIR}/{short}/{rel}", data))

    write(f"{short}.eqg", archive.to_bytes())
    for new, data in maps.values():
        write(new, data)
    write(f"{short}.zone.json", (json.dumps(sidecar, indent=2) + "\n").encode("utf-8"))
    if not maps:
        result.warnings.append("no_map_files")

    result.format = check_eqg(result.eqg_path, spec, sidecar_path=result.sidecar_path,
                              expected_name=short)
    if result.format.passed:
        _after_check(result, spec, root)
    return result
