"""
generators/rebuild.py
---------------------
A partial rebuild (partial-rebuild Req 2.2, 4.1, task 3): the next version of a zone built
from a version's saved stages when only its Props change (a new decor seed, or one room's own
decor seed), or an edit's spec (zone-generator-edits, ``build_spec``).

    parent v<n>/<name>.spec.json  ->  ZoneSpec (+ decor layers), the change applied
    parent v<n>/<name>.eqg        ->  its TER bytes and surface textures (SavedStages)
    parent v<n>/<name>.zone.json  ->  the Texture_Mode that drew each surface
                                  ->  generate_validated(..., stages=...)  ->  v<n+1>

The build skips texture drawing (``ZoneBuilder.build``'s ``stages``) and runs everything
after it as any build does: Sites, trees, Decor, the ZON, the Pack, the sidecar, the GLB,
then the full gate, the format check, the map files and the move into the version folder.
The result equals a full build of the same request and seeds byte for byte, footer aside
(archive decision 2; ``tests/test_partial_rebuild.py`` proves it per zone type). A pinned
decor seed that fails the gate is reported (``GenerationFailed``), never rerolled, and leaves
no version folder, as in any pinned build.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from core.pfs import PfsArchive
from generators.builder import SavedStages, StaleStages, with_decor_layers
from generators.zone_spec import ZoneSpec

__all__ = ["SHELLS", "NoSavedStages", "ShellCache", "StaleStages", "build_spec", "rebuild_decor",
           "room_ids", "room_seeds_after", "saved_spec", "saved_stages"]


class ShellCache:
    """The kept gate results of a few TERs, for this process (partial-rebuild Req 4.2, 4.4):
    per TER, the room gate's mesh part (``analyzer.traverse.Shell``) and the map outline
    (``mapgeom.extract_outline``'s result). A bounded LRU: a 16-room shell holds tens of MB.

    The key is the TER bytes' hash (not the version: two versions with one TER share it),
    with the agent and what the gate reads of the spec besides the mesh (the rooms, the
    corridors, the safe point and the race whose height a transition is judged by), so a
    kept result is only ever reused for the same question. A shell never outlives the
    process: the first rebuild after a restart runs the full gate."""

    def __init__(self, size: int = 4):
        self.size = size
        self._entries: "OrderedDict[tuple, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def key(ter_bytes: bytes, spec: ZoneSpec, agent: Any) -> Tuple[str, str, str]:
        from analyzer.traverse import AgentModel

        doc = spec.to_dict()
        asks = json.dumps({"rooms": doc["rooms"], "corridors": doc["corridors"],
                           "safe_point": doc["safe_point"],
                           "dungeon_race": doc.get("dungeon_race")},
                          sort_keys=True, default=str)
        return (hashlib.sha256(ter_bytes).hexdigest(), repr(agent or AgentModel()),
                hashlib.sha256(asks.encode("utf-8")).hexdigest())

    def _get(self, key, what: str):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.get(what) is None:
                return None
            self._entries.move_to_end(key)
            return entry[what]

    def _put(self, key, what: str, value) -> None:
        with self._lock:
            entry = self._entries.setdefault(key, {})
            entry[what] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self.size:
                self._entries.popitem(last=False)

    def shell(self, key):
        """The kept ``Shell`` for ``key``, or ``None``."""
        return self._get(key, "shell")

    def keep_shell(self, key, shell) -> None:
        """Keep ``shell`` under ``key`` (its mesh drawn and its TER let go first)."""
        shell.key = key
        self._put(key, "shell", shell.keep())

    def outline(self, key):
        """The kept map outline (an ``OutlineSet``, before ``with_solids``) for ``key``."""
        return self._get(key, "outline")

    def keep_outline(self, key, outline) -> None:
        self._put(key, "outline", outline)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


#: The Server process's kept shells and outlines.
SHELLS = ShellCache()


class NoSavedStages(LookupError):
    """The parent version lacks a file a partial rebuild reads (its spec, ``.eqg`` or
    sidecar), or one of them can't be read: rebuild it on the full path instead."""


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NoSavedStages(f"{path.name}: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise NoSavedStages(f"{path.name}: not an object")
    return data


def saved_spec(parent_dir: Path, name: str) -> dict:
    """The parent's ``<name>.spec.json``: ``ZoneSpec.to_dict`` plus ``decor_layers``."""
    return _read_json(Path(parent_dir) / f"{name}.spec.json")


def room_ids(spec_doc: Mapping[str, Any]) -> List[str]:
    """The ids of a saved spec's rooms: the ones a room decor seed can name."""
    return [str(r.get("id")) for r in spec_doc.get("rooms") or () if isinstance(r, Mapping)]


def room_seeds_after(old: Optional[Mapping[str, int]], changes: Mapping[str, Any]) -> Dict[str, int]:
    """The room decor seeds after ``changes``: a new ``decor_seed`` clears them (every room's
    Props change with it), then ``room_decor: {room, decor_seed}`` adds or replaces one."""
    seeds = {} if changes.get("decor_seed") is not None else {str(k): int(v) for k, v in (old or {}).items()}
    one = changes.get("room_decor")
    if one is not None:
        seeds[str(one["room"])] = int(one["decor_seed"])
    return seeds


def _apply(spec_doc: Mapping[str, Any], changes: Mapping[str, Any]) -> dict:
    """The spec dict with ``changes`` applied (``decor_seed``, ``room_decor``)."""
    doc = dict(spec_doc)
    if changes.get("decor_seed") is not None:
        doc["decor_seed"] = int(changes["decor_seed"])
    one = changes.get("room_decor")
    if one is not None and str(one["room"]) not in room_ids(doc):
        raise KeyError(one["room"])
    seeds = room_seeds_after(doc.get("room_decor_seeds"), changes)
    doc.pop("room_decor_seeds", None)
    if seeds:
        doc["room_decor_seeds"] = seeds
    return doc


def saved_stages(parent_dir: Path, name: str) -> SavedStages:
    """The parent's TER bytes and surface textures from its ``.eqg``, and each surface's
    Texture_Mode from its sidecar's Texture_Manifest."""
    parent_dir = Path(parent_dir)
    try:
        arc = PfsArchive.from_file(parent_dir / f"{name}.eqg")
    except (OSError, ValueError) as exc:
        raise NoSavedStages(f"{name}.eqg: {type(exc).__name__}") from None
    ter = arc.get(f"ter_{name}.ter")
    if ter is None:
        raise NoSavedStages(f"{name}.eqg has no ter_{name}.ter")
    textures = {f.name.lower(): f.data for f in arc.get_by_extension("dds")}
    manifest = _read_json(parent_dir / f"{name}.zone.json").get("textures") or []
    modes = {e["material"]: e["texture_mode"] for e in manifest
             if isinstance(e, Mapping) and "material" in e and "texture_mode" in e}
    return SavedStages(ter, textures, modes)


def rebuild_decor(parent_dir: Path, changes: Mapping[str, Any], *, zone_id: str,
                  generate: Optional[Callable[..., Any]] = None, **pipeline: Any):
    """Build the next version of ``zone_id`` from ``parent_dir`` (a version folder) with its
    Props changed: ``changes`` names a new ``decor_seed`` and/or one ``room_decor: {room,
    decor_seed}`` (``room_seeds_after``). The parent's spec is loaded (with its decor
    layers), the change applied, and the zone built through ``generate`` (default
    ``pipeline.generate_validated``) with the parent's stages and its seed pinned; the rest
    of ``pipeline`` (``zone_type``, ``version``, ``output_dir``, ``request``,
    ``version_meta``, ...) goes to it as is. Returns its ``ValidatedBuild``.

    Raises ``NoSavedStages`` when the parent lacks a file this reads, ``KeyError`` for a
    room the parent has none of, ``StaleStages`` (from the build) when the parent's TER
    isn't what this code builds from its spec, and ``GenerationFailed`` (pinned) when the
    build fails a gate."""
    doc = _apply(saved_spec(parent_dir, zone_id.lower()), changes)
    return build_spec(parent_dir, doc, zone_id=zone_id, generate=generate, **pipeline)


def build_spec(parent_dir: Path, doc: Mapping[str, Any], *, zone_id: str, stages: bool = True,
               generate: Optional[Callable[..., Any]] = None, **pipeline: Any):
    """Build the next version of ``zone_id`` from a whole spec dict ``doc`` (a version's
    ``<name>.spec.json`` as an edit left it, ``decor_layers`` included), its seed pinned.
    With ``stages`` the parent's saved stages (``parent_dir``'s TER and textures) build it,
    as ``rebuild_decor`` does; without, it is a full build of ``doc``. Either way the result
    is the same zone byte for byte, footer aside, or ``StaleStages`` when the parent's TER
    isn't what ``doc`` builds (zone-generator-edits decision 4: the caller builds it again
    without ``stages``). Raises as ``rebuild_decor``."""
    if generate is None:
        from generators.pipeline import generate_validated as generate
    name = zone_id.lower()
    doc = dict(doc)
    layers = tuple(doc.pop("decor_layers", None) or ())
    saved = saved_stages(parent_dir, name) if stages else None
    seed = doc.get("seed")
    if seed is None:
        raise NoSavedStages(f"{name}.spec.json has no seed")
    if pipeline.get("seed") not in (None, seed):
        raise ValueError(f"a partial rebuild keeps the parent's seed {seed}, not {pipeline['seed']}")
    pipeline["seed"] = seed

    text = json.dumps(doc)

    def factory(s: int) -> ZoneSpec:
        # A fresh copy per attempt: a build writes into its spec.
        return with_decor_layers(ZoneSpec.from_dict(json.loads(text)), layers)

    return generate(factory, zone_id=zone_id, stages=saved, **pipeline)
