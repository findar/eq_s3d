"""
generators/textures/recipes.py
------------------------------
Texture recipes (interesting textures spec Requirement 3): which Texture_Family
draws a dungeon or city material, and with what parameters.

``styles/texture_recipes.json`` holds the data. ``resolve(name)`` splits a
Material_Name into its Texture_Set and Surface and finds the most specific
entry: an exact ``set``, else the longest ``theme`` the set equals or ends in
(``_<theme>``), else the Surface's fallback family. Wilderness (``wild_*``,
``liquid_*``) and tree (``veg_*``) materials aren't room-graph surfaces and
resolve to ``None``: they keep step 3's texture path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RECIPES_PATH = Path(__file__).resolve().parent.parent.parent / "styles" / "texture_recipes.json"
SURFACES = ("floor", "wall", "ceiling")


class RecipeError(ValueError):
    """The recipe file is malformed; the message names the field."""


@dataclass(frozen=True)
class Recipe:
    """A resolved recipe: the family, its merged parameters, and how it was
    found (``set``, ``theme`` or ``fallback``)."""
    family: str
    params: Dict[str, Any] = field(default_factory=dict, hash=False, compare=True)
    source: str = "fallback"


@dataclass(frozen=True)
class _Entry:
    key: str            # "set" or "theme"
    value: str
    surface: str
    family: str
    params: Tuple[Tuple[str, Any], ...]


@dataclass(frozen=True)
class RecipeBook:
    families: Dict[str, Dict[str, Any]]
    entries: Tuple[_Entry, ...]
    fallback: Dict[str, str]

    def resolve(self, name: str) -> Optional[Recipe]:
        """The recipe for Material_Name *name*, or ``None`` for a name that
        isn't ``<set>_<floor|wall|ceiling>``."""
        tex_set, _, surface = name.rpartition("_")
        if surface not in SURFACES or not tex_set:
            return None
        exact = [e for e in self.entries
                 if e.key == "set" and e.surface == surface and e.value == tex_set]
        themed = sorted((e for e in self.entries
                         if e.key == "theme" and e.surface == surface
                         and (tex_set == e.value or tex_set.endswith("_" + e.value))),
                        key=lambda e: len(e.value), reverse=True)
        for source, hits in (("set", exact), ("theme", themed)):
            if hits:
                e = hits[0]
                return Recipe(e.family, {**self.families[e.family], **dict(e.params)}, source)
        family = self.fallback[surface]
        return Recipe(family, dict(self.families[family]), "fallback")


def parse_recipes(doc: Dict[str, Any]) -> RecipeBook:
    """Validate a recipe document; raise ``RecipeError`` naming the bad field."""
    if not isinstance(doc, dict):
        raise RecipeError("recipes: expected an object")
    families = doc.get("families")
    if not isinstance(families, dict) or not families:
        raise RecipeError("families: expected a non-empty object")
    for fam, params in families.items():
        if not isinstance(params, dict):
            raise RecipeError(f"families.{fam}: expected an object of parameters")

    entries: List[_Entry] = []
    materials = doc.get("materials")
    if not isinstance(materials, list):
        raise RecipeError("materials: expected a list")
    for i, m in enumerate(materials):
        where = f"materials[{i}]"
        if not isinstance(m, dict):
            raise RecipeError(f"{where}: expected an object")
        keys = [k for k in ("set", "theme") if k in m]
        if len(keys) != 1 or not isinstance(m[keys[0]], str) or not m[keys[0]]:
            raise RecipeError(f"{where}: needs exactly one of 'set' or 'theme'")
        surface = m.get("surface")
        if surface not in SURFACES:
            raise RecipeError(f"{where}.surface: must be one of {', '.join(SURFACES)}")
        family = m.get("family")
        if family not in families:
            raise RecipeError(f"{where}.family: unknown family {family!r}")
        params = m.get("params", {})
        if not isinstance(params, dict):
            raise RecipeError(f"{where}.params: expected an object")
        unknown = set(params) - set(families[family])
        if unknown:
            raise RecipeError(f"{where}.params: {sorted(unknown)} not parameters of {family}")
        entries.append(_Entry(keys[0], m[keys[0]], surface, family,
                              tuple(sorted(params.items()))))

    fallback = doc.get("fallback")
    if not isinstance(fallback, dict):
        raise RecipeError("fallback: expected an object")
    for surface in SURFACES:
        if fallback.get(surface) not in families:
            raise RecipeError(f"fallback.{surface}: must name a family")
    return RecipeBook(dict(families), tuple(entries), {s: fallback[s] for s in SURFACES})


@lru_cache(maxsize=1)
def load_recipes(path: Optional[str] = None) -> RecipeBook:
    p = Path(path) if path else RECIPES_PATH
    return parse_recipes(json.loads(p.read_text(encoding="utf-8")))


def resolve(name: str) -> Optional[Recipe]:
    """Recipe for Material_Name *name* from the shipped recipe file."""
    return load_recipes().resolve(name)
