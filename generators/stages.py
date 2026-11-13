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
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from generators.world import Socket, World

#: Socket kinds in the order they attach (Req 3.3): the Apron digs the ground before the
#: Sites see it, and Sites keep off the Tunnel and Apron.
ORDER = ("root", "hillside", "ground")


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
    and its Terrain edits (the Apron)."""
    socket: str
    kind: str
    layout: Any = None
    warnings: List[str] = field(default_factory=list)
    entrance: Any = None
    envelope: Any = None
    rooms_requested: int = 0
    edits: List[TerrainEdit] = field(default_factory=list)


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
                      edits=[apron_edit(world, socket, grid, entrance)])


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
    """``world`` with every Terrain edit of ``attachments`` applied, in order: the height
    grid's moved vertices and the Spawn (``World.spawn`` and the ``ground`` Socket's point
    and ``spawn``). ``world`` itself is not changed. ``bowl_heights`` (the grid before the
    water bed sinks) is left as it is: no edit digs within a cell of water.

    The Attach stage applies them before the next Socket, the Build before it makes the TER:
    one function, so the two see the same ground."""
    edits = [e for a in attachments for e in a.edits]
    if not edits:
        return world
    if world.terrain is None:
        raise ValueError("Terrain edits need a World with terrain")
    heights = world.terrain.heights.copy()
    spawn = world.spawn
    for e in edits:
        for i, j, z in e.cells:
            heights[i, j] = z
        if e.spawn is not None:
            spawn = tuple(e.spawn)
    sockets = []
    for s in world.sockets:
        if s.kind == "ground" and spawn != world.spawn:
            s = replace(s, x=spawn[0], y=spawn[1], z=spawn[2],
                        ground=dict(s.ground, spawn=list(spawn)))
        sockets.append(s)
    return replace(world, terrain=replace(world.terrain, heights=heights), spawn=spawn,
                   sockets=sockets)


__all__ = ["Attachment", "ORDER", "TerrainEdit", "apply_edits", "apron_edit", "attach_rooms"]
