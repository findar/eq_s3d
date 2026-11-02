"""
generators/outdoor_dungeon.py
-----------------------------
The outdoor dungeon's Envelope, built from the host terrain (outdoor-dungeon
design "Envelope", task 4).

A host-hill wilderness spec (``wilderness_spec(..., landform=...)``) is built
to its TER; the Envelope's surface is that TER, interpolated exactly as the
client walks it (two triangles per quad, split along the (i, j)-(i+1, j+1)
diagonal), not the design matrix. The footprint is the hill region: a disc at
the placed Landform's centre out to where its relief falls to half (radius
plus half the flank). The Rock_Cover and floor limit are the survey defaults
(design finding 4).

``layout_in_envelope`` sizes the rooms to the Envelope, not to the dungeon
style profile's whole-zone floor area (which would give rooms the size of
the hill), so the default room count fits.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Tuple

import numpy as np

from core.ter import TerFile
from generators.envelope import Envelope
from generators.layout import LayoutGenerator
from generators.wilderness.build import landscape_for
from generators.wilderness.matrix import Landform
from generators.zone_spec import ZoneSpec

#: Minimum terrain left above any ceiling (design finding 4: stock p10 rock
#: is 12-22 u).
ROCK_COVER: float = 24.0
#: How far below the Entrance's floor the dungeon may reach (finding 4:
#: covered floor sits at most ~130 u below the open ground near it).
FLOOR_DEPTH: float = 150.0
#: Rooms laid out under the default Host_Hill.
DEFAULT_ROOMS: int = 5
#: Mean room side as a share of the Envelope's inradius, before dividing by
#: sqrt(room count): the rooms' combined floor is about this share squared
#: of the inradius square, leaving room for separation and corridors.
ROOM_FILL: float = 0.6
#: Room height (the layout's ceiling) under a hill. The dungeon profile's
#: 121 u leaves too thin a band under the flank; 80 u is still ~13 player
#: heights, and 5 rooms then fit every seed sampled (0.8 fill or 121 u
#: rooms drop rooms on a few).
ROOM_HEIGHT: float = 80.0

_SIDE_STEP = {"N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}


def ter_surface(ter: TerFile, origin: Tuple[float, float], resolution: float,
                shape: Tuple[int, int]) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    """Height of a heightfield TER at XY, vectorised.

    The TER's first ``nx * ny`` vertices are the grid (vertex ``i * ny + j``
    at the centre of fine cell ``(i, j)``); later vertices (the water surface)
    are ignored. Each quad is two triangles split along its (i, j)-(i+1, j+1)
    diagonal, as ``build_wilderness_ter`` emits them. Points beyond the grid
    take the nearest edge's height."""
    nx, ny = shape
    z = np.array([v.z for v in ter.vertices[:nx * ny]], dtype=np.float64).reshape(nx, ny)
    ox, oy = origin
    res = float(resolution)

    def surface(x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        fx = np.clip((x - ox) / res - 0.5, 0.0, nx - 1.0)
        fy = np.clip((y - oy) / res - 0.5, 0.0, ny - 1.0)
        i = np.minimum(np.floor(fx).astype(int), nx - 2)
        j = np.minimum(np.floor(fy).astype(int), ny - 2)
        u, v = fx - i, fy - j
        za, zb = z[i, j], z[i + 1, j]
        zc, zd = z[i + 1, j + 1], z[i, j + 1]
        lower = za + u * (zb - za) + v * (zc - zb)      # triangle a-b-c (u >= v)
        upper = za + v * (zd - za) + u * (zc - zd)      # triangle a-c-d (v > u)
        return np.where(u >= v, lower, upper)

    return surface


def host_footprint(landform: Landform, sides: int = 64) -> Tuple[Tuple[float, float], ...]:
    """The hill region: a ``sides``-gon at the Landform's centre out to where
    its relief falls to half (``radius + flank / 2``)."""
    cx, cy = landform.centre
    r = landform.radius + landform.flank / 2.0
    return tuple((cx + r * math.cos(2 * math.pi * k / sides),
                  cy + r * math.sin(2 * math.pi * k / sides)) for k in range(sides))


def approach_foot(landform: Landform) -> Tuple[float, float]:
    """Where the Landform's flank meets the open ground on its approach side."""
    dx, dy = _SIDE_STEP[landform.approach]
    reach = landform.radius + landform.flank
    return landform.centre[0] + dx * reach, landform.centre[1] + dy * reach


def host_envelope(spec: ZoneSpec, ter: TerFile, *,
                  rock_cover: float = ROCK_COVER,
                  entrance_floor: Optional[float] = None) -> Envelope:
    """The Envelope under a host-hill spec's built terrain.

    ``entrance_floor`` defaults to the TER height at the hill's foot on the
    approach side (the open ground the Entrance will open onto); the floor
    limit is ``FLOOR_DEPTH`` below it."""
    land = landscape_for(spec)
    landform = land.matrix.landform
    if landform is None:
        raise ValueError(f"spec {spec.name!r} has no Landform to build an Envelope under")
    surface = ter_surface(ter, land.synth.origin, land.synth.resolution,
                          land.bowl.heights.shape)
    if entrance_floor is None:
        fx, fy = approach_foot(landform)
        entrance_floor = float(surface(fx, fy))
    return Envelope(host_footprint(landform), entrance_floor - FLOOR_DEPTH,
                    surface, rock_cover)


def layout_in_envelope(name: str, seed: Optional[int], envelope: Envelope,
                       room_count: int = DEFAULT_ROOMS,
                       **kwargs) -> Tuple[ZoneSpec, List[str]]:
    """A box-dungeon layout inside ``envelope``, rooms sized to it.

    The mean room side is ``ROOM_FILL * inradius / sqrt(room_count)``, set
    through the generator's size multiplier. Returns the layout and the
    generator's warnings (``rooms_reduced`` when rooms were dropped)."""
    gen = LayoutGenerator("dungeon", seed=seed)
    gen.ceiling = ROOM_HEIGHT
    gen._apply_room_scale(room_count)
    base = (gen.room_min + gen.room_max) / 2.0
    gen.size_multiplier = ROOM_FILL * envelope.inradius / math.sqrt(room_count) / base
    spec = gen.generate(name, room_count=room_count, envelope=envelope, **kwargs)
    return spec, list(gen.warnings)
