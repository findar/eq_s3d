"""
analyzer/zonelist.py
--------------------
The Known_Zone_List: the zone short names an Export can take over.

The list is bundled as ``analyzer/data/rof2_zones.json`` (short name, container,
long name). It is made ONCE from a RoF2 install by::

    python -m analyzer.zonelist --write [--eq-path F:\\everquest_rof2]

and committed (step 17 amendment A2). It holds names and container only, never
client bytes. At run time :func:`known_shortnames` reads the bundled list and
sets ``in_install`` from the configured install (``EQ_PATH``); the run-time scan
never adds or drops names. Nothing under the install is ever written.

What counts as a zone archive (umbrella design, "Known short names"):

* a ``<stem>.s3d`` holding ``<stem>.wld``;
* a ``<stem>.eqg`` holding a ``.zon`` or a ``ter_*.ter``, or with a loose
  ``<stem>.zon`` beside it;

minus the companion archives (``*_obj*``, ``*_chr*``, ``*_lit``, ``*_assets``,
``gequip*``, ``global*``). Two more families hold ``<stem>.wld`` but are not
zones, so they are dropped too: the other equipment archives (``*equip*``:
``lgequip``, ``ldonequip``, ``vequip``, ...) and ``sky.s3d`` (the sky dome).

Long names come from the client's zone table in ``eqgame.exe`` when it can be
read (each zone is registered by a call that pushes the long name, then the
short name; see :func:`_long_names_from_exe`). Only the two strings are kept.
A zone the table doesn't name keeps an empty long name.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from core.pfs import _DIR_SENTINEL_CRC, _PFS_MAGIC, _inflate_chunks

DATA_PATH: Path = Path(__file__).resolve().parent / "data" / "rof2_zones.json"

#: The default Target_Shortname: a small, rarely visited zone with no
#: progression, flag or key dependency (decided by the user).
DEFAULT_TARGET: str = "arena"

#: The install the --write scan reads when neither --eq-path nor EQ_PATH says.
FALLBACK_INSTALL = r"F:\everquest_rof2"

_COMPANION = re.compile(r".*_obj.*|.*_chr.*|.*_lit|.*_assets|.*equip.*|global.*|sky")


@dataclass(frozen=True)
class KnownZone:
    shortname: str       # e.g. "arena"
    long_name: str       # e.g. "The Arena"; "" when unknown
    container: str       # "s3d" | "eqg": the stock zone's client format
    in_install: bool     # found under EQ_PATH (False when no install is configured)


# ---------------------------------------------------------------------------
# Run time: the bundled list
# ---------------------------------------------------------------------------

_cache: Dict[Optional[str], Dict[str, KnownZone]] = {}


def _install_from_env() -> Optional[Path]:
    """``EQ_PATH`` (environment or ``.env``), or None when unset or missing."""
    from core.env import env_value

    value = env_value("EQ_PATH")
    if not value or not Path(value).is_dir():
        return None
    return Path(value)


def _load_bundled(path: Path = DATA_PATH) -> List[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["zones"]


def known_shortnames(eq_path: Path | str | None = None) -> Dict[str, KnownZone]:
    """The Known_Zone_List, keyed by lower-case short name.

    ``in_install`` is true when the zone's stock archive (``<short>.<container>``)
    is in ``eq_path``, else in ``EQ_PATH``; with no install every entry is false.
    Cached per process (per install).
    """
    root = Path(eq_path) if eq_path else _install_from_env()
    if root is not None and not root.is_dir():
        root = None
    key = str(root) if root else None
    if key in _cache:
        return _cache[key]
    present = set()
    if root is not None:
        present = {p.name.lower() for p in root.iterdir() if p.is_file()}
    zones = {}
    for row in _load_bundled():
        short = row["shortname"].lower()
        zones[short] = KnownZone(
            shortname=short,
            long_name=row.get("long_name", ""),
            container=row["container"],
            in_install=f"{short}.{row['container']}" in present,
        )
    _cache[key] = zones
    return zones


def is_known(shortname: str, eq_path: Path | str | None = None) -> bool:
    """Whether ``shortname`` (any case) is on the Known_Zone_List."""
    return (shortname or "").strip().lower() in known_shortnames(eq_path)


def closest(name: str, n: int = 5) -> List[str]:
    """Up to ``n`` known short names closest to ``name`` (for an error message)."""
    names = sorted(known_shortnames())
    target = (name or "").strip().lower()
    hits = difflib.get_close_matches(target, names, n=n, cutoff=0.6)
    if len(hits) < n and target:
        hits += [s for s in names if s.startswith(target[:3]) and s not in hits][: n - len(hits)]
    return hits[:n]


# ---------------------------------------------------------------------------
# --write: scan an install
# ---------------------------------------------------------------------------

def archive_names(path: Path) -> List[str]:
    """The lower-case file names inside a PFS archive (``.s3d``/``.eqg``).

    Inflates only the name block, never the files. ``[]`` when unreadable.
    """
    try:
        data = Path(path).read_bytes()
        if len(data) < 12 or data[4:8] != _PFS_MAGIC:
            return []
        (dir_offset,) = struct.unpack_from("<I", data, 0)
        (count,) = struct.unpack_from("<I", data, dir_offset)
        for i in range(count):
            crc, offset, size = struct.unpack_from("<III", data, dir_offset + 4 + i * 12)
            if crc != _DIR_SENTINEL_CRC:
                continue
            block = _inflate_chunks(data[offset:], size)
            (n,) = struct.unpack_from("<I", block, 0)
            names, pos = [], 4
            for _ in range(n):
                (ln,) = struct.unpack_from("<I", block, pos)
                pos += 4
                names.append(block[pos:pos + ln].rstrip(b"\x00").decode("ascii", "replace").lower())
                pos += ln
            return names
    except (OSError, struct.error, zlib.error, ValueError):
        return []
    return []


def is_companion(stem: str) -> bool:
    return _COMPANION.fullmatch(stem.lower()) is not None


def scan_install(eq_path: Path) -> Dict[str, str]:
    """``{short name: container}`` for every zone archive in ``eq_path``.

    A stem with both a zone ``.s3d`` and a zone ``.eqg`` is recorded as ``eqg``.
    """
    root = Path(eq_path)
    files = {p.name.lower(): p for p in root.iterdir() if p.is_file()}
    found: Dict[str, str] = {}
    for name, p in sorted(files.items()):
        stem, _, ext = name.rpartition(".")
        if ext not in ("s3d", "eqg") or not stem or is_companion(stem):
            continue
        inner = archive_names(p)
        if ext == "s3d":
            if f"{stem}.wld" in inner and stem not in found:
                found[stem] = "s3d"
        else:
            if (any(n.endswith(".zon") for n in inner)
                    or any(n.startswith("ter_") and n.endswith(".ter") for n in inner)
                    or f"{stem}.zon" in files):
                found[stem] = "eqg"
    return found


def _long_names_from_exe(exe: Path, shortnames: Iterable[str]) -> Dict[str, str]:
    """Long names from the client's zone table in ``eqgame.exe``.

    The client registers each zone with a call whose arguments push the long
    name and then the short name (``68 <long> 68 <short>``, 32-bit). For every
    short name in ``shortnames`` this finds that pair and reads the long-name
    string. Only the two strings are used. ``{}`` when the file can't be read.
    """
    try:
        d = Path(exe).read_bytes()
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        nsec = struct.unpack_from("<H", d, pe + 6)[0]
        optsz = struct.unpack_from("<H", d, pe + 20)[0]
        opt = pe + 24
        if struct.unpack_from("<H", d, opt)[0] != 0x10B:  # PE32 only
            return {}
        base = struct.unpack_from("<I", d, opt + 28)[0]
        secs = []
        for i in range(nsec):
            o = opt + optsz + i * 40
            vsz, va, rsz, raw = struct.unpack_from("<IIII", d, o + 8)
            secs.append((base + va, max(vsz, rsz), raw, rsz))
    except (OSError, struct.error):
        return {}

    def off_to_va(off: int) -> Optional[int]:
        for va, _vsz, raw, rsz in secs:
            if raw <= off < raw + rsz:
                return va + off - raw
        return None

    def va_to_off(v: int) -> Optional[int]:
        for va, vsz, raw, rsz in secs:
            if va <= v < va + min(vsz, rsz):
                return v - va + raw
        return None

    def cstr(v: int) -> Optional[str]:
        o = va_to_off(v)
        if o is None:
            return None
        e = d.find(b"\x00", o, o + 128)
        if e < 0:
            return None
        try:
            s = d[o:e].decode("ascii")
        except UnicodeDecodeError:
            return None
        return s if s.isprintable() else None

    out: Dict[str, str] = {}
    for short in shortnames:
        for m in re.finditer(b"\x00" + re.escape(short.encode("ascii")) + b"\x00", d):
            va = off_to_va(m.start() + 1)
            if va is None:
                continue
            push = b"\x68" + struct.pack("<I", va)
            at = d.find(push)
            while at >= 5 and short not in out:
                if d[at - 5] == 0x68:
                    long_name = cstr(struct.unpack_from("<I", d, at - 4)[0])
                    if long_name:
                        out[short] = long_name
                at = d.find(push, at + 1)
            if short in out:
                break
    return out


def build_list(eq_path: Path) -> List[dict]:
    """The rows ``--write`` commits: sorted by short name."""
    zones = scan_install(eq_path)
    longs = _long_names_from_exe(Path(eq_path) / "eqgame.exe", zones)
    return [{"shortname": s, "long_name": longs.get(s, ""), "container": c}
            for s, c in sorted(zones.items())]


def write_list(eq_path: Path, out: Path = DATA_PATH) -> List[dict]:
    """Scan ``eq_path`` and write the bundled list to ``out`` (never under the install)."""
    from core.paths import assert_output_allowed

    assert_output_allowed(Path(out).parent, Path(eq_path))
    rows = build_list(eq_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "about": "RoF2 zone short names found in an install by `python -m analyzer.zonelist "
                 "--write`: names and container only. long_name is from the client's zone "
                 "table (eqgame.exe), empty when it names none.",
        "default_target": DEFAULT_TARGET,
        "zones": rows,
    }
    # One zone per line, so a rescan's diff reads row by row.
    body = ",\n".join("  " + json.dumps(r) for r in rows)
    head = json.dumps({k: v for k, v in doc.items() if k != "zones"}, indent=1)[:-2]
    out.write_text(f'{head},\n "zones": [\n{body}\n ]\n}}\n', encoding="utf-8")
    _cache.clear()
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analyzer.zonelist",
                                 description="The Known_Zone_List (RoF2 zone short names).")
    ap.add_argument("--write", action="store_true",
                    help=f"scan the install and write {DATA_PATH.name}")
    ap.add_argument("--eq-path", help=f"the install (default EQ_PATH, else {FALLBACK_INSTALL})")
    args = ap.parse_args(argv)
    if args.write:
        root = Path(args.eq_path) if args.eq_path else (_install_from_env() or Path(FALLBACK_INSTALL))
        if not root.is_dir():
            print(f"no install at {root}", file=sys.stderr)
            return 2
        rows = write_list(root)
        named = sum(1 for r in rows if r["long_name"])
        print(f"wrote {len(rows)} zones ({named} with a long name) to {DATA_PATH}")
        return 0
    for z in known_shortnames().values():
        print(f"{z.shortname:20} {z.container:4} {'*' if z.in_install else ' '} {z.long_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
