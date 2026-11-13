"""The stage driver (roadmap step 12, world-sockets design "The Attach stage",
"Order and Terrain edits", "Where the stages run").

A zone is made in stages: the World (``generators.world``), then the Attach stage, which
attaches rooms and Sites to the World's Sockets in a fixed order (:data:`ORDER`: the
``hillside`` before the ``ground``), then the Build. This module holds that order, the
Attach stage's results (:class:`Attachment`, with its :class:`TerrainEdit` s), and the one
function that applies an Attachment's Terrain edits to a World (:func:`apply_edits`), which
the Attach stage uses before the next Socket and the Build uses when it makes the TER, so the
two can't disagree.

Attaching rooms to a ``hillside`` Socket (:func:`attach_rooms`) reads only the World (its
height grid, Spawn), the Socket, the plan's room fields and the seed: no landscape is
synthesized and no TER is built (Req 2.4, 3.1).

Attaching Sites to the ``ground`` Socket (:func:`attach_sites`) reads the World with every
earlier Attachment's Terrain edits applied and the Socket, whose ``keep_clear`` holds the
Kept_Clear shapes those Attachments added (the outdoor dungeon's hill, Tunnel and Apron):
P6, Req 3.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from generators.world import Socket, World

#: Socket kinds in the order they attach (Req 3.3): the Apron digs the ground before the
#: Sites see it, and Sites keep off the Tunnel and Apron.
ORDER = ("root", "hillside", "ground")

#: A Kept_Clear shape: the capsule of radius ``r`` round ``(x0, y0)-(x1, y1)``.
ClearShape = Tuple[float, float, float, float, float]


def rooms_seed(seed: int, rooms: Optional[int] = None) -> int:
    """The Attach stage's seed: the one the Sites salt their stream from (and, from task 7,
    the rooms' layout). ``rooms`` is the zone's ``rooms_seed``; unset, it is the zone's
    ``seed``, so every build keeps its bytes (Req 6.1)."""
    return int(seed if rooms is None else rooms)


@dataclass
class TerrainEdit:
    """A change an Attachment makes to its World: the grid vertices it moves (``cells``:
    ``(i, j, z)``, the new height of vertex ``(i, j)`` of the World's height grid, exact) and,
    when the edit reaches the Spawn, the Spawn after it (``spawn``; ``None`` when it stays).
    The outdoor dungeon's Apron is one: the dug trench in front of the Mouth."""
    socket: str
    cells: Tuple[Tuple[int, int, float], ...] = ()
    spawn: Optional[Tuple[float, float, float]] = None


@dataclass
class Attachment:
    """What attaching to one Socket made. For a ``hillside`` Socket: the dungeon's layout (a
    ``ZoneSpec`` holding the rooms, corridors, lights, gates, materials and layout record the
    host spec gets), the layout's warnings, the Entrance, the Envelope it was laid out in
    (its ``floor_limit`` and ``rock_cover`` are what the spec records), the rooms asked for,
    its Terrain edits (the Apron) and the Kept_Clear shapes later Sockets keep off
    (``keep_clear``: the hill, Tunnel and Apron). For a ``ground`` Socket: the Sites
    (``sites``, a ``SitePlacement``)."""
    socket: str
    kind: str
    layout: Any = None
    warnings: List[str] = field(default_factory=list)
    entrance: Any = None
    envelope: Any = None
    rooms_requested: int = 0
    edits: List[TerrainEdit] = field(default_factory=list)
    keep_clear: Tuple[ClearShape, ...] = ()
    sites: Any = None


def attach_rooms(world: World, socket: Socket, fields: Mapping[str, Any],
                 seed: Optional[int], engine=None) -> Attachment:
    """A dungeon attached to ``world``'s ``hillside`` Socket ``socket`` (Req 3.1): laid out in
    the Envelope under the hill, fitted to the grid and given its Entrance, then the Apron as
    a Terrain edit.

    ``fields`` are the plan's room fields: ``room_count``, ``verticality``, ``name`` (the
    layout's), and the layout's own keywords (``locks``, ``dungeon_theme``,
    ``dungeon_race``, ``elemental_tint``). ``seed`` lays the rooms out; ``engine`` is the
    Layout_Engine (``None`` is classic). The Envelope's floor limit comes from the dungeon's
    own verticality and race when the engine stacks (``outdoor_dungeon.floor_depth``),
    step 5's ``FLOOR_DEPTH`` otherwise.

    Reads only the World's height grid and Spawn and the Socket. Raises one of
    ``outdoor_dungeon.PLAN_ERRORS``, naming the Socket, when the hill can't take the
    dungeon (the pipeline retries on a fresh seed)."""
    from generators import outdoor_dungeon as od

    if socket.kind != "hillside" or "dungeon" not in socket.accepts:
        raise ValueError(f"Socket {socket.id!r} ({socket.kind}) doesn't take a dungeon")
    if world.terrain is None:
        raise ValueError(f"Socket {socket.id!r}: its World has no terrain")
    kwargs = dict(fields)
    name = kwargs.pop("name", "dungeon")
    room_count = kwargs.pop("room_count", od.DEFAULT_ROOMS)
    verticality = kwargs.pop("verticality", None)
    depth = od.FLOOR_DEPTH
    if getattr(engine, "stacking", False):
        depth = od.floor_depth(verticality, kwargs.get("dungeon_race") or "")
    grid = od.socket_grid(socket, world.terrain)
    try:
        envelope = od.host_envelope(socket, grid, depth=depth)
        layout, warnings, entrance = od.plan_dungeon(socket, grid, envelope, name, seed,
                                                     room_count, engine=engine, **kwargs)
    except od.PLAN_ERRORS as e:
        raise type(e)(f"Socket {socket.id!r}: {e}") from e
    return Attachment(socket=socket.id, kind=socket.kind, layout=layout,
                      warnings=list(warnings), entrance=entrance, envelope=envelope,
                      rooms_requested=room_count,
                      edits=[apron_edit(world, socket, grid, entrance)],
                      keep_clear=entrance_keep_clear(world, socket, entrance))


def entrance_attachment(world: World, socket: Socket, entrance) -> Attachment:
    """What an outdoor dungeon's planned ``entrance`` adds to ``world`` at its ``hillside``
    Socket: the Apron as a Terrain edit and the hill, Tunnel and Apron as Kept_Clear. The
    build reads the Entrance off the spec (the rooms were attached in ``plan_to_spec``) and
    applies this before the ground Socket attaches; its edit and shapes are the ones
    :func:`attach_rooms` made."""
    from generators.outdoor_dungeon import socket_grid

    if world.terrain is None:
        raise ValueError(f"Socket {socket.id!r}: its World has no terrain")
    grid = socket_grid(socket, world.terrain)
    return Attachment(socket=socket.id, kind=socket.kind, entrance=entrance,
                      edits=[apron_edit(world, socket, grid, entrance)],
                      keep_clear=entrance_keep_clear(world, socket, entrance))


def entrance_keep_clear(world: World, socket: Socket, entrance) -> Tuple[ClearShape, ...]:
    """What Sites keep off round an outdoor dungeon (POIs spec Req 7), as capsules: the
    Host_Hill's footprint disc (the Socket's placed Landform); the Tunnel, wall to portal;
    and the Mouth and Apron, from the portal out over the most rows the Apron digs and one
    row more. The Tunnel's and Apron's capsules are the dug strip's half-width plus
    ``outdoor_dungeon.SITE_CLEAR``.

    The rows the Apron digs are found on the grid before the water bed sinks
    (``Terrain.undrowned``), as ``outdoor_dungeon.keep_clear_shapes`` finds them on the
    landscape's bowl: the same floats, so the same shapes."""
    from generators.outdoor_dungeon import SITE_CLEAR, _apron, _Grid
    from generators.wilderness.matrix import Landform

    lf = Landform.from_dict(socket.ground["landform"])
    g = socket.ground
    grid = _Grid.of(world.terrain.undrowned, g["origin"], g["res"])
    e = entrance
    ox, oy = grid.origin
    res = grid.res
    dug = np.any(_apron(grid, e)[0] < grid.z - 1e-9, axis=1 - e.axis)
    rows = [k for k in np.nonzero(dug)[0]]
    reach = max((abs(int(k) - e.portal) for k in rows), default=1)

    def coord(axis: int, k: float) -> float:
        return (ox, oy)[axis] + (k + 0.5) * res

    def pt(run: float, cross: float) -> Tuple[float, float]:
        return (run, cross) if e.axis == 0 else (cross, run)

    mid = (coord(1 - e.axis, e.cross) + coord(1 - e.axis, e.cross + 1)) / 2.0
    portal = coord(e.axis, e.portal)
    far = coord(e.axis, e.portal + e.outward * (reach + 1))
    hill = (lf.centre[0], lf.centre[1], lf.centre[0], lf.centre[1], lf.radius + lf.flank / 2.0)
    tunnel = (*pt(e.wall, mid), *pt(portal, mid), res / 2.0 + SITE_CLEAR)
    # The Apron's trench spans the strip's two columns and one either side.
    apron = (*pt(portal, mid), *pt(far, mid), 2.0 * res + SITE_CLEAR)
    return (hill, tunnel, apron)


def attach_sites(world: World, socket: Socket, seed: int, *, biome: str = "plains",
                 control: str = "normal", inhabitant: str = "", rules=None) -> Attachment:
    """The Sites attached to ``world``'s ``ground`` Socket ``socket`` (Req 3.2, 3.3).

    ``world`` has every earlier Attachment's edits applied (:func:`apply_edits`), so the
    Sites stand on the dug ground and keep off the Socket's ``keep_clear`` shapes. ``seed``
    is :func:`rooms_seed`'s: the Sites salt their own stream from it. Reads only the World's
    terrain and the Socket."""
    from generators.sites.placement import place_sites

    if socket.kind != "ground" or "site" not in socket.accepts:
        raise ValueError(f"Socket {socket.id!r} ({socket.kind}) doesn't take Sites")
    if world.terrain is None:
        raise ValueError(f"Socket {socket.id!r}: its World has no terrain")
    placement = place_sites(world.terrain, socket, seed, biome=biome, control=control,
                            inhabitant=inhabitant, rules=rules)
    return Attachment(socket=socket.id, kind=socket.kind, sites=placement)


def apron_edit(world: World, socket: Socket, grid, entrance) -> TerrainEdit:
    """The Apron in front of ``entrance``'s Mouth as a Terrain edit of ``world``: the grid
    vertices it lowers, and the Spawn's new height when the dug ground reaches it (it drops
    by as much as the ground under it does)."""
    from generators.outdoor_dungeon import _apron, _grid_surface

    dug, _ = _apron(grid, entrance)
    cells = tuple((int(i), int(j), float(dug[i, j]))
                  for i, j in np.argwhere(dug != grid.z))
    sx, sy, sz = world.spawn
    before = float(_grid_surface(grid.z, grid.origin, grid.res)(sx, sy))
    after = float(_grid_surface(dug, grid.origin, grid.res)(sx, sy))
    spawn = (sx, sy, sz + after - before) if after < before else None
    return TerrainEdit(socket=socket.id, cells=cells, spawn=spawn)


def apply_edits(world: World, attachments: Sequence[Attachment]) -> World:
    """``world`` with every Terrain edit and Kept_Clear shape of ``attachments`` applied, in
    order: the height grid's moved vertices, the Spawn (``World.spawn`` and the ``ground``
    Socket's point and ``spawn``), and each Attachment's ``keep_clear`` added to the
    ``ground`` Socket's. ``world`` itself is not changed. ``bowl_heights`` (the grid before
    the water bed sinks) is left as it is: no edit digs within a cell of water.

    The Attach stage applies them before the next Socket, the Build before it makes the TER:
    one function, so the two see the same ground."""
    edits = [e for a in attachments for e in a.edits]
    shapes = [list(s) for a in attachments for s in a.keep_clear]
    if not edits and not shapes:
        return world
    heights = None
    spawn = world.spawn
    if edits:
        if world.terrain is None:
            raise ValueError("Terrain edits need a World with terrain")
        heights = world.terrain.heights.copy()
        for e in edits:
            for i, j, z in e.cells:
                heights[i, j] = z
            if e.spawn is not None:
                spawn = tuple(e.spawn)
    sockets = []
    for s in world.sockets:
        if s.kind == "ground":
            ground = dict(s.ground)
            if shapes:
                ground["keep_clear"] = list(ground.get("keep_clear", [])) + shapes
            if spawn != world.spawn:
                s = replace(s, x=spawn[0], y=spawn[1], z=spawn[2],
                            ground=dict(ground, spawn=list(spawn)))
            else:
                s = replace(s, ground=ground)
        sockets.append(s)
    terrain = world.terrain if heights is None else replace(world.terrain, heights=heights)
    return replace(world, terrain=terrain, spawn=spawn, sockets=sockets)


__all__ = ["Attachment", "ClearShape", "ORDER", "TerrainEdit", "apply_edits", "apron_edit",
           "attach_rooms", "attach_sites", "entrance_attachment", "entrance_keep_clear",
           "rooms_seed"]
