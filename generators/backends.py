"""
generators/backends.py
-----------------------
Geometry backend registry (wave 3).

A *geometry backend* turns a :class:`~generators.zone_spec.ZoneSpec` into a
``TerFile`` ground/structure mesh. There are exactly two:

  * ``BoxBackend``     — the box-mesh builder used by dungeon and city zones.
  * ``TerrainBackend`` — the heightfield terrain builder used by wilderness
    zones. It returns ``None`` when its hard dependency (``numpy``) can't be
    imported, so a machine without numpy degrades to the box backend instead
    of crashing.

The ``BACKENDS`` dict is keyed by the canonical zone-type vocabulary
(:data:`generators.zone_types.DEFINED_ZONE_TYPES`) — dungeon→Box, city→Box,
wilderness→Terrain. There is NO cave backend (cave was removed in M0; it
returns as a dungeon archetype / natural style later). ``backend_for`` resolves
a zone type to its backend, falling back to the dungeon (Box) backend for any
undefined/unknown value — consistent with the ``canonical_zone_type`` →
``dungeon`` default used everywhere else.

This replaces the old ``ZoneBuilder._TERRAIN_THEMES`` set: routing is now a
registry lookup, not a membership test.
"""

from __future__ import annotations

from typing import Optional, Protocol

from core.ter import TerFile
from .zone_spec import ZoneSpec
from .geometry import build_mesh
from .zone_types import DEFINED_ZONE_TYPES

# numpy is the terrain backend's hard dependency. Guard the import here so a
# machine without numpy degrades gracefully: TerrainBackend.build returns None
# and the builder falls back to the box backend with a warning, rather than
# raising an ImportError mid-build.
try:  # pragma: no cover - exercised only on a numpy-less machine
    import numpy as _np  # noqa: F401

    _NUMPY_AVAILABLE = True
except Exception:  # pragma: no cover
    _NUMPY_AVAILABLE = False


class GeometryBackend(Protocol):
    """The interface ``ZoneBuilder._build_geometry`` routes through.

    A backend is stateless and exposes a ``name`` and a ``build`` that returns
    the finished ``TerFile`` — or ``None`` when the backend can't run (e.g.
    terrain without numpy), signalling the caller to fall back to the box
    backend.
    """

    name: str

    def build(self, spec: ZoneSpec, ter_name: str,
              ter_version: int) -> Optional[TerFile]:
        ...


class BoxBackend:
    """Box-mesh backend (dungeon, city). Always available."""

    name = "box"

    def build(self, spec: ZoneSpec, ter_name: str,
              ter_version: int) -> Optional[TerFile]:
        mesh = build_mesh(spec)
        return mesh.to_ter(name=ter_name, version=ter_version)


class TerrainBackend:
    """Heightfield terrain backend (wilderness).

    Returns ``None`` when numpy is unavailable so the builder can fall back to
    the box backend. The terrain is sized to the room footprint plus a generous
    margin — identical sizing to the pre-registry ``_build_terrain`` so this
    refactor produces the same mesh for the normal (numpy-present) path. (The
    terrain REFRAME into the room-graph frame is a later task; here it still
    builds in its current frame.)
    """

    name = "terrain"

    def build(self, spec: ZoneSpec, ter_name: str,
              ter_version: int) -> Optional[TerFile]:
        if not _NUMPY_AVAILABLE:
            return None

        # An open-world wilderness spec (it carries a ``wilderness`` payload)
        # builds from the wilderness pipeline; every other spec takes the
        # room-footprint terrain path below, unchanged.
        if spec.wilderness is not None:
            from .wilderness.build import build_wilderness_ter
            return build_wilderness_ter(spec, ter_name, ter_version)

        # Imported lazily: terrain.py imports numpy at module load, which would
        # raise on a numpy-less machine before we get the chance to degrade.
        from .field.terrain import TerrainSpec, build_terrain

        # Size the terrain to the room footprint plus a generous margin.
        if spec.rooms:
            xs = [r.center_x for r in spec.rooms]
            ys = [r.center_y for r in spec.rooms]
            margin = 600.0
            width = max(1200.0, (max(xs) - min(xs)) + 2 * margin)
            depth = max(1200.0, (max(ys) - min(ys)) + 2 * margin)
        else:
            width = depth = 2000.0

        seed = spec.seed & 0x7FFFFFFF if spec.seed is not None \
            else _stable_name_seed(ter_name)

        tspec = TerrainSpec(
            width=width,
            depth=depth,
            resolution=50.0,
            seed=seed,
            height_scale=360.0,
            noise_scale=max(500.0, min(width, depth) * 0.4),
            max_walkable_grad=0.85,
        )
        ter = build_terrain(tspec, name=ter_name)
        if ter is not None:
            ter.version = ter_version
        return ter


def _stable_name_seed(ter_name: str) -> int:
    """Stable 31-bit seed from the ter name (for specs carrying no seed).

    Mirrors ``ZoneBuilder._base_seed``'s fallback so an unseeded spec builds
    the same terrain through the registry as it did through ``_build_terrain``.
    The name passed in is ``ter_<zone>``; the historical fallback hashed the
    bare ``<zone>`` name, so strip the ``ter_`` prefix to match byte-for-byte.
    """
    import zlib

    bare = ter_name[4:] if ter_name.startswith("ter_") else ter_name
    return zlib.crc32(bare.encode("utf-8")) & 0x7FFFFFFF


# zone_type -> backend. Keyed by the canonical vocabulary; no cave backend.
BACKENDS: dict[str, GeometryBackend] = {
    "dungeon": BoxBackend(),
    "city": BoxBackend(),
    "wilderness": TerrainBackend(),
}

# Sanity: the registry must cover exactly the defined zone types.
assert set(BACKENDS) == set(DEFINED_ZONE_TYPES), (
    "BACKENDS keys must equal DEFINED_ZONE_TYPES"
)


def backend_for(zone_type: object) -> GeometryBackend:
    """Return the backend for ``zone_type``; undefined/unknown → box (dungeon).

    Matches the project-wide convention that an undefined zone type falls back
    to ``dungeon`` (see ``canonical_zone_type``), so an unrecognised value
    builds a box zone rather than erroring.
    """
    if isinstance(zone_type, str):
        backend = BACKENDS.get(zone_type)
        if backend is not None:
            return backend
    return BACKENDS["dungeon"]
