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

The SQL script and the bundle (tasks 4 and 6) hang off :func:`_after_check`,
the one place that runs only when the format check passes. Until then
``ExportResult.sql_written`` stays false.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from analyzer.rof2check import FormatReport, check_eqg
from analyzer.zonelist import DEFAULT_TARGET, closest, is_known
from core.paths import OutputRoot
from core.pfs import PfsArchive
from core.zon import ZonFile
from generators.zone_spec import ZoneSpec

#: The sub-folder of a build directory that holds its Exports.
EXPORT_DIR = "export"

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
    sql_written: bool = False         # task 4/6: the SQL script
    warnings: List[str] = field(default_factory=list)

    @property
    def eqg_path(self) -> Path:
        return self.dir / f"{self.shortname}.eqg"

    @property
    def sidecar_path(self) -> Path:
        return self.dir / f"{self.shortname}.zone.json"


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


def _after_check(result: ExportResult, spec: ZoneSpec, root: OutputRoot) -> None:
    """Runs only when the exported archive passed the Format_Checker (Req 2.2).

    Task 6 adds the SQL script (``sqlexport.export_sql``, then
    ``result.sql_written = True``) and the bundle here."""
    return None


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
    result = ExportResult(shortname=short, dir=out_dir)

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
