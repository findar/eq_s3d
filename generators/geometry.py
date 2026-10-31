"""
generators/geometry.py
----------------------
Procedural mesh generation. Converts RoomSpec / CorridorSpec into vertices and
triangles, accumulating them into a MeshBuilder that can emit a TerFile.

Everything is built from axis-aligned boxes (rooms and corridors), with inward-
facing walls so the player sees textured surfaces from inside.

EQ coordinate convention: Z is up. Winding order is counter-clockwise when
viewed from the visible side.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.ter import TerFile, Material, Vertex, Polygon, MAGIC_TERRAIN
from .zone_spec import ZoneSpec, RoomSpec, CorridorSpec, MaterialSpec
from .routing import corridor_route


# A sloped corridor floor is subdivided so each segment rises at most this much
# in Z. A single tall ramp quad splits into two triangles whose centroids sit
# dz/3 apart in Z; the traversability agent (step-up ~3u) then reads its own
# ramp as an unclimbable gap. Fine segments keep every walkable face within a
# small step of its neighbour so a ramp is actually walkable end to end.
MAX_SEG_RISE = 2.5


# ---------------------------------------------------------------------------
# Mesh builder
# ---------------------------------------------------------------------------

class MeshBuilder:
    """
    Accumulates geometry and resolves materials, then emits a TerFile.

    Vertices are deduplicated only implicitly (each quad adds its own 4 verts).
    This keeps the generator simple; the resulting mesh is still valid.
    """

    def __init__(self):
        self.vertices: List[Vertex] = []
        self.polygons: List[Polygon] = []
        self._material_index: Dict[str, int] = {}
        self.materials: List[Material] = []

    # ------------------------------------------------------------------
    # Material resolution
    # ------------------------------------------------------------------

    def material_id(self, mat_spec: MaterialSpec) -> int:
        """Return the index for a material, registering it if new."""
        if mat_spec.name in self._material_index:
            return self._material_index[mat_spec.name]
        idx = len(self.materials)
        mat = Material(index=idx, name=mat_spec.name, shader=mat_spec.shader)
        mat.add_diffuse(mat_spec.texture)
        self.materials.append(mat)
        self._material_index[mat_spec.name] = idx
        return idx

    # ------------------------------------------------------------------
    # Primitive: a textured quad (two triangles)
    # ------------------------------------------------------------------

    def add_quad(self,
                 p0: Tuple[float, float, float],
                 p1: Tuple[float, float, float],
                 p2: Tuple[float, float, float],
                 p3: Tuple[float, float, float],
                 normal: Tuple[float, float, float],
                 material: int,
                 uv_scale: float = 0.01,
                 flags: int = 0) -> None:
        """
        Add a quad defined by four corners in CCW order (viewed from the
        visible side, i.e. the side the normal points toward).

        UVs are planar-projected based on world position * uv_scale so textures
        tile consistently regardless of surface size.
        """
        base = len(self.vertices)
        corners = [p0, p1, p2, p3]

        # Planar UV projection: pick the two axes most perpendicular to normal
        nx, ny, nz = (abs(normal[0]), abs(normal[1]), abs(normal[2]))
        if nz >= nx and nz >= ny:
            uv_axes = (0, 1)   # floor/ceiling → use XY
        elif nx >= ny:
            uv_axes = (1, 2)   # east/west wall → use YZ
        else:
            uv_axes = (0, 2)   # north/south wall → use XZ

        for cx, cy, cz in corners:
            coords = (cx, cy, cz)
            u = coords[uv_axes[0]] * uv_scale
            v = coords[uv_axes[1]] * uv_scale
            self.vertices.append(Vertex(
                x=cx, y=cy, z=cz,
                nx=normal[0], ny=normal[1], nz=normal[2],
                u=u, v=v,
            ))

        # Two triangles: (0,1,2) and (0,2,3)
        self.polygons.append(Polygon(base + 0, base + 1, base + 2, material, flags))
        self.polygons.append(Polygon(base + 0, base + 2, base + 3, material, flags))

    # ------------------------------------------------------------------
    # Primitive: a hollow box room
    # ------------------------------------------------------------------

    def add_room(self, room: RoomSpec, spec: ZoneSpec) -> None:
        """Build a hollow box with inward-facing walls, floor, and ceiling."""
        (x0, y0, z0), (x1, y1, z1) = room.bounds

        floor_mat   = self.material_id(spec.materials[room.floor_material])
        wall_mat    = self.material_id(spec.materials[room.wall_material])
        ceiling_mat = self.material_id(spec.materials[room.ceiling_material])

        # Floor — normal points up (+Z), CCW from above
        self.add_quad(
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            normal=(0, 0, 1), material=floor_mat,
        )
        # Ceiling — normal points down (-Z), CCW from below
        self.add_quad(
            (x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1),
            normal=(0, 0, -1), material=ceiling_mat,
        )

        # Walls (inward-facing). A side in open_walls is cut only where a
        # corridor meets it: wall pieces either side of each doorway and a
        # lintel above it, so the floor never ends at a drop beside a door. An
        # open side no corridor reaches (hand-authored specs) stays fully open.
        doors = _door_openings(room, spec)
        extents = {
            "S": (x0, x1), "N": (x0, x1),   # along X
            "W": (y0, y1), "E": (y0, y1),   # along Y
        }
        for side in ("S", "N", "W", "E"):
            lo, hi = extents[side]
            if side not in room.open_walls:
                self._add_room_wall(room, side, lo, hi, z0, z1, wall_mat)
                continue
            cuts = _merge_openings(doors.get(side, []), lo, hi)
            if not cuts:
                continue
            pos = lo
            for c0, c1, top in cuts:
                if c0 > pos:
                    self._add_room_wall(room, side, pos, c0, z0, z1, wall_mat)
                if top < z1:
                    self._add_room_wall(room, side, c0, c1, top, z1, wall_mat)
                pos = c1
            if pos < hi:
                self._add_room_wall(room, side, pos, hi, z0, z1, wall_mat)

    def _add_room_wall(self, room: RoomSpec, side: str, a: float, b: float,
                       lo: float, hi: float, wall_mat: int) -> None:
        """One inward-facing rectangle of a room wall, spanning a..b along the
        wall (a < b) and lo..hi in Z. Corner order matches the whole-wall quads
        so an uncut wall is byte-identical to the historic build."""
        (x0, y0, _), (x1, y1, _) = room.bounds
        if side == "S":     # y = y0, normal +Y
            self.add_quad((a, y0, lo), (a, y0, hi), (b, y0, hi), (b, y0, lo),
                          normal=(0, 1, 0), material=wall_mat)
        elif side == "N":   # y = y1, normal -Y
            self.add_quad((b, y1, lo), (b, y1, hi), (a, y1, hi), (a, y1, lo),
                          normal=(0, -1, 0), material=wall_mat)
        elif side == "W":   # x = x0, normal +X
            self.add_quad((x0, b, lo), (x0, b, hi), (x0, a, hi), (x0, a, lo),
                          normal=(1, 0, 0), material=wall_mat)
        else:               # "E": x = x1, normal -X
            self.add_quad((x1, a, lo), (x1, a, hi), (x1, b, hi), (x1, b, lo),
                          normal=(-1, 0, 0), material=wall_mat)

    # ------------------------------------------------------------------
    # Primitive: a corridor (floor + ceiling + two side walls)
    # ------------------------------------------------------------------

    def add_corridor(self, cor: CorridorSpec, spec: ZoneSpec) -> None:
        """
        Build a corridor between two wall openings, picking one of three routes
        so the corridor meets BOTH openings perpendicularly and at the right
        floor height:

        * **Straight** — the openings are (near) collinear on the run axis: a
          single axis-aligned leg.
        * **Z-corridor** (3 segments) — both rooms face each other on PARALLEL
          walls (both E/W, or both N/S). This is the common layout case. A
          single-corner L cannot serve it: one of its legs would run *along* a
          wall face instead of out through the opening, so it meets that opening
          at the wrong XY and (for elevation) the wrong floor height, leaving a
          gap (seed 1955208177). Instead we emit a perpendicular stub straight
          out of wall A, a middle cross-jog, and a perpendicular stub into wall
          B. Each end stub stays flat at its own room's floor; the middle jog
          carries the entire elevation change.
        * **L-bend** (2 segments) — the genuine cross-axis case (one opening on
          an E/W wall, the other on an N/S wall). A single corner serves it: a
          perpendicular leg out of A, then a perpendicular leg into B.

        For every route the whole height change (ramp or staircase) is confined
        to ONE segment via the shared `_emit_route` helper, so that segment
        lands flush with its room while the flat segments sit exactly at the
        other room's floor — no gap at either opening, and ramp/stair behave
        identically regardless of route.
        """
        floor_mat   = self.material_id(spec.materials[cor.floor_material])
        wall_mat    = self.material_id(spec.materials[cor.wall_material])
        ceiling_mat = self.material_id(spec.materials[cor.ceiling_material])

        hw = cor.width / 2

        # The straight / Z / L decision (and which leg carries the rise) lives
        # in generators.routing.corridor_route, shared with the layout's leg
        # measurement and the continuity/terrain consumers. A Route's
        # carry == -1 means "carry the longest leg", which _emit_route spells
        # as carry=None.
        route = corridor_route(cor, {r.id: r for r in spec.rooms})
        z_carry = None if route.carry < 0 else route.carry

        self._emit_route(
            list(route.waypoints), list(route.axes), carry=z_carry,
            from_z=cor.from_z, to_z=cor.to_z,
            hw=hw, height=cor.height, steps=cor.steps,
            floor_mat=floor_mat, wall_mat=wall_mat, ceiling_mat=ceiling_mat)

    @staticmethod
    def _seg_len(waypoints, k):
        (x0, y0), (x1, y1) = waypoints[k], waypoints[k + 1]
        return abs(x1 - x0) + abs(y1 - y0)   # axis-aligned → one term is 0

    @classmethod
    def _waypoint_zs(cls, waypoints, carry, from_z, to_z):
        """Floor height at each waypoint, and the resolved carry leg: from_z up
        to (and including) the start of the carry leg, to_z from the end of the
        carry leg onward. `carry` None means the longest leg."""
        n_legs = len(waypoints) - 1
        if carry is None:
            carry = max(range(n_legs), key=lambda k: cls._seg_len(waypoints, k))
        zs = [from_z if i <= carry else to_z for i in range(len(waypoints))]
        return zs, carry

    def _emit_route(self, waypoints, axes, carry, from_z, to_z, hw, height,
                    steps, floor_mat, wall_mat, ceiling_mat):
        """
        Shared multi-segment corridor builder. `waypoints` is an ordered list of
        (x, y) points (>= 2); each consecutive pair is one axis-aligned leg, and
        `axes[k]` is True when leg k runs along X.

        The ENTIRE elevation change (and the staircase, if any) is confined to
        leg `carry`: every leg before it stays flat at `from_z`, every leg after
        stays flat at `to_z`. This single rule keeps ramps and stairs behaving
        identically across the straight / Z / L routes — the carry leg lands
        flush with its room, the flat legs sit exactly at the other room's
        floor, so there is no gap at either opening — regardless of WHICH leg
        carries. We therefore default `carry` to the LONGEST leg, which gives
        the gentlest ramp grade / most room for stair treads without disturbing
        the flush landings (seed 481893615 verified both openings stay flush).
        Each bend is a flat corridor-wide square at the waypoint's height, and
        the legs stop at its edge (`_leg_ends`), so no ramp overlaps a flat
        bend floor and the carry leg's slope runs only between the squares.
        The square is walled on the two sides no leg leaves through: without
        those walls the outer corner of every bend was a hole (task 14).
        """
        zs, carry = self._waypoint_zs(waypoints, carry, from_z, to_z)

        for k in range(len(waypoints) - 1):
            ends = self._leg_ends(waypoints, k, hw, zs)
            if ends is None:
                continue   # the bend squares already cover this short leg
            (x0, y0), (x1, y1) = ends
            leg_steps = steps if k == carry else 0
            self._add_straight_leg(
                x0, y0, zs[k], x1, y1, zs[k + 1],
                axes[k], hw, height, leg_steps,
                floor_mat, wall_mat, ceiling_mat)

        # Fill each interior corner flush with the shared floor height there.
        for i in range(1, len(waypoints) - 1):
            self._add_corner_fill(self._bend_square(waypoints, i, hw), zs[i],
                                  height, floor_mat, ceiling_mat)
            self._add_corner_walls(waypoints, axes, i, zs[i], hw, height,
                                   wall_mat)

    @staticmethod
    def _leg_ends(waypoints, k, hw, zs):
        """The built span of leg k: its waypoints, each end that is a bend
        pulled back by `hw` to the bend square's edge (a doorway end is kept).
        None when nothing is left between the squares.

        A leg that rises (`zs[k] != zs[k + 1]`) but is shorter than the two
        squares is built at full length instead, so the rise isn't lost. The
        layout never makes one (its grade cap gives such a jog no rise); a
        hand-authored spec can."""
        n_legs = len(waypoints) - 1
        (x0, y0), (x1, y1) = waypoints[k], waypoints[k + 1]
        length = abs(x1 - x0) + abs(y1 - y0)   # axis-aligned → one term is 0
        t0 = hw if k > 0 else 0.0
        t1 = hw if k < n_legs - 1 else 0.0
        if length - t0 - t1 <= 1e-6:
            if length > 1e-6 and abs(zs[k + 1] - zs[k]) > 0.01:
                return (waypoints[k], waypoints[k + 1])
            return None
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        return ((x0 + ux * t0, y0 + uy * t0), (x1 - ux * t1, y1 - uy * t1))

    @staticmethod
    def _bend_square(waypoints, i, hw):
        """The floor square of the bend at waypoint i, (x0, y0, x1, y1): a
        corridor width across, centred on the waypoint, but cut back to a
        doorway it would overhang (a doorway leg shorter than `hw`), so the
        corridor floor never reaches past its opening into the room."""
        cx, cy = waypoints[i]
        x0, y0, x1, y1 = cx - hw, cy - hw, cx + hw, cy + hw
        last = len(waypoints) - 1
        for j in (i - 1, i + 1):
            if j not in (0, last):
                continue
            px, py = waypoints[j]
            if abs(px - cx) >= abs(py - cy):
                if px > cx:
                    x1 = min(x1, max(px, cx))
                else:
                    x0 = max(x0, min(px, cx))
            elif py > cy:
                y1 = min(y1, max(py, cy))
            else:
                y0 = max(y0, min(py, cy))
        return (x0, y0, x1, y1)

    def _add_corner_walls(self, waypoints, axes, i, cz, hw, height, wall_mat):
        """Wall the bend square at waypoint i on its closed sides.

        The two sides facing the previous and next waypoints are where the
        legs join, so they stay open. The other two are walled, except where
        another part of the corridor's floor lies right past them (a second
        bend square sharing an edge when the jog is shorter than a corridor
        width, and the leg leaving it).
        """
        cx, cy = waypoints[i]
        sq = self._bend_square(waypoints, i, hw)
        # Floor rectangles of the rest of the route: every leg at full length,
        # every other bend square.
        others = []
        for k in range(len(waypoints) - 1):
            (ax, ay), (bx, by) = waypoints[k], waypoints[k + 1]
            if axes[k]:
                others.append((min(ax, bx), ay - hw, max(ax, bx), ay + hw))
            else:
                others.append((ax - hw, min(ay, by), ax + hw, max(ay, by)))
        for j in range(1, len(waypoints) - 1):
            if j != i:
                others.append(self._bend_square(waypoints, j, hw))

        def toward(p):
            """The side of the square facing waypoint p."""
            dx, dy = p[0] - cx, p[1] - cy
            if abs(dx) >= abs(dy):
                return "E" if dx > 0 else "W"
            return "N" if dy > 0 else "S"

        open_sides = {toward(waypoints[i - 1]), toward(waypoints[i + 1])}
        eps = 1e-6
        for side in ("S", "N", "W", "E"):
            if side in open_sides:
                continue
            along_x = side in "SN"
            plane = {"S": sq[1], "N": sq[3], "W": sq[0], "E": sq[2]}[side]
            out = -1.0 if side in "SW" else 1.0
            lo, hi = (sq[0], sq[2]) if along_x else (sq[1], sq[3])
            covered = []
            for (rx0, ry0, rx1, ry1) in others:
                # Does this rectangle hold the floor just outside the side?
                n0, n1 = (ry0, ry1) if along_x else (rx0, rx1)
                inside = (n0 <= plane + eps and n1 > plane + eps) if out > 0 \
                    else (n0 < plane - eps and n1 >= plane - eps)
                if inside:
                    c0, c1 = (rx0, rx1) if along_x else (ry0, ry1)
                    c0, c1 = max(lo, c0), min(hi, c1)
                    if c1 > c0:
                        covered.append((c0, c1))
            pos = lo
            for c0, c1 in sorted(covered) + [(hi, hi)]:
                if c0 > pos + eps:
                    self._add_bend_wall(side, plane, pos, c0, cz, cz + height,
                                        wall_mat)
                pos = max(pos, c1)

    def _add_bend_wall(self, side, plane, a, b, lo, hi, wall_mat):
        """One wall rectangle on side `side` of a bend square, a..b along the
        side, lo..hi in Z, facing into the square."""
        if side == "S":     # y = plane, normal +Y
            self.add_quad((a, plane, lo), (a, plane, hi), (b, plane, hi),
                          (b, plane, lo), normal=(0, 1, 0), material=wall_mat)
        elif side == "N":   # y = plane, normal -Y
            self.add_quad((b, plane, lo), (b, plane, hi), (a, plane, hi),
                          (a, plane, lo), normal=(0, -1, 0), material=wall_mat)
        elif side == "W":   # x = plane, normal +X
            self.add_quad((plane, b, lo), (plane, b, hi), (plane, a, hi),
                          (plane, a, lo), normal=(1, 0, 0), material=wall_mat)
        else:               # "E": x = plane, normal -X
            self.add_quad((plane, a, lo), (plane, a, hi), (plane, b, hi),
                          (plane, b, lo), normal=(-1, 0, 0), material=wall_mat)

    def _add_straight_leg(self, fx, fy, fz, tx, ty, tz, along_x, hw, height,
                          steps, floor_mat, wall_mat, ceiling_mat):
        """
        Build one straight axis-aligned leg between two points that share the
        cross coordinate (collinear along the run axis). Ramps or steps between
        fz and tz. This is the single-segment primitive both straight and
        L-shaped corridors are built from.
        """
        if along_x:
            if fx <= tx:
                a_pos, a_z, b_pos, b_z = fx, fz, tx, tz
            else:
                a_pos, a_z, b_pos, b_z = tx, tz, fx, fz
            cross = fy
        else:
            if fy <= ty:
                a_pos, a_z, b_pos, b_z = fy, fz, ty, tz
            else:
                a_pos, a_z, b_pos, b_z = ty, tz, fy, fz
            cross = fx
        c0, c1 = cross - hw, cross + hw

        # Degenerate leg (zero length) — nothing to build.
        if abs(b_pos - a_pos) < 1e-6:
            return

        if steps > 0 and abs(b_z - a_z) > 0.01:
            self._add_stepped_corridor(a_pos, a_z, b_pos, b_z, c0, c1,
                                       height, steps, along_x,
                                       floor_mat, wall_mat, ceiling_mat)
        else:
            self._add_ramp_corridor(a_pos, a_z, b_pos, b_z, c0, c1,
                                    height, along_x,
                                    floor_mat, wall_mat, ceiling_mat)

    def _add_corner_fill(self, square, cz, height, floor_mat, ceiling_mat):
        """
        Fill the square where two perpendicular legs meet, so the floor and
        ceiling are continuous through the bend (no hole at the corner).
        `square` is the bend's (x0, y0, x1, y1) from `_bend_square`.
        """
        x0, y0, x1, y1 = square
        # Floor
        self.add_quad((x0, y0, cz), (x1, y0, cz), (x1, y1, cz), (x0, y1, cz),
                      normal=(0, 0, 1), material=floor_mat)
        # Ceiling
        zc = cz + height
        self.add_quad((x0, y1, zc), (x1, y1, zc), (x1, y0, zc), (x0, y0, zc),
                      normal=(0, 0, -1), material=ceiling_mat)

    def _seg_quad(self, along_x, pos0, pos1, c0, c1, z_lo0, z_lo1, zc0, zc1,
                  floor_mat, wall_mat, ceiling_mat):
        """
        Build one segment of a corridor between pos0..pos1 (along the run axis),
        with floor heights z_lo0/z_lo1 and ceiling heights zc0/zc1 at each end.
        """
        if along_x:
            # Run axis = X, cross axis = Y
            # Floor (slopes from z_lo0 to z_lo1), normal roughly +Z
            self.add_quad((pos0, c0, z_lo0), (pos1, c0, z_lo1),
                          (pos1, c1, z_lo1), (pos0, c1, z_lo0),
                          normal=(0, 0, 1), material=floor_mat)
            # Ceiling
            self.add_quad((pos0, c1, zc0), (pos1, c1, zc1),
                          (pos1, c0, zc1), (pos0, c0, zc0),
                          normal=(0, 0, -1), material=ceiling_mat)
            # South wall (c0), normal +Y
            self.add_quad((pos0, c0, z_lo0), (pos0, c0, zc0),
                          (pos1, c0, zc1), (pos1, c0, z_lo1),
                          normal=(0, 1, 0), material=wall_mat)
            # North wall (c1), normal -Y
            self.add_quad((pos1, c1, z_lo1), (pos1, c1, zc1),
                          (pos0, c1, zc0), (pos0, c1, z_lo0),
                          normal=(0, -1, 0), material=wall_mat)
        else:
            # Run axis = Y, cross axis = X
            self.add_quad((c0, pos0, z_lo0), (c1, pos0, z_lo0),
                          (c1, pos1, z_lo1), (c0, pos1, z_lo1),
                          normal=(0, 0, 1), material=floor_mat)
            self.add_quad((c0, pos1, zc1), (c1, pos1, zc1),
                          (c1, pos0, zc0), (c0, pos0, zc0),
                          normal=(0, 0, -1), material=ceiling_mat)
            # West wall (c0), normal +X
            self.add_quad((c0, pos1, z_lo1), (c0, pos1, zc1),
                          (c0, pos0, zc0), (c0, pos0, z_lo0),
                          normal=(1, 0, 0), material=wall_mat)
            # East wall (c1), normal -X
            self.add_quad((c1, pos0, z_lo0), (c1, pos0, zc0),
                          (c1, pos1, zc1), (c1, pos1, z_lo1),
                          normal=(-1, 0, 0), material=wall_mat)

    def _add_ramp_corridor(self, a_pos, a_z, b_pos, b_z, c0, c1, height,
                           along_x, floor_mat, wall_mat, ceiling_mat):
        """
        Sloped floor from (a_pos, a_z) to (b_pos, b_z), subdivided along the run
        into segments that each rise at most MAX_SEG_RISE. The subdivision is
        what makes a ramp walkable to the per-triangle traversability agent: a
        single quad would present a dz/3 step between its two triangles, read as
        an unclimbable gap. Visually it is still a smooth ramp.
        """
        dz = abs(b_z - a_z)
        n = max(1, int(math.ceil(dz / MAX_SEG_RISE)))
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            p0 = a_pos + (b_pos - a_pos) * t0
            p1 = a_pos + (b_pos - a_pos) * t1
            z0 = a_z + (b_z - a_z) * t0
            z1 = a_z + (b_z - a_z) * t1
            self._seg_quad(along_x, p0, p1, c0, c1,
                           z0, z1, z0 + height, z1 + height,
                           floor_mat, wall_mat, ceiling_mat)

    def _add_stepped_corridor(self, a_pos, a_z, b_pos, b_z, c0, c1, height,
                              steps, along_x, floor_mat, wall_mat, ceiling_mat):
        """
        Staircase from (a_pos, a_z) up/down to (b_pos, b_z): `steps` flat treads
        connected by vertical risers.

        Tread i sits at height `a_z + i*rise` (so the FIRST tread is flush with
        the lower floor and the LAST tread's far edge reaches b_z — no gap at
        either landing). The riser is at the far edge of each tread and climbs
        to the next tread's height. The riser normal faces back down the run so
        it is visible to someone ascending.
        """
        total_run = b_pos - a_pos
        total_rise = b_z - a_z
        run_per_step = total_run / steps
        rise_per_step = total_rise / steps

        for i in range(steps):
            p0 = a_pos + i * run_per_step
            p1 = a_pos + (i + 1) * run_per_step
            z_tread = a_z + i * rise_per_step            # this tread's height
            z_next = a_z + (i + 1) * rise_per_step        # next tread's height
            # Ceiling follows the ascending treads so headroom stays constant.
            zc0 = z_tread + height
            zc1 = z_next + height

            # Flat tread (floor + ceiling + side walls) at constant z_tread.
            self._seg_quad(along_x, p0, p1, c0, c1,
                           z_tread, z_tread, zc0, zc1,
                           floor_mat, wall_mat, ceiling_mat)

            # Vertical riser at the FAR edge of this tread, climbing to the
            # next tread's height. The final riser (i == steps-1) climbs to b_z
            # so the staircase lands flush with the upper floor — no gap at the
            # top landing.
            if abs(z_next - z_tread) > 1e-6:
                lo, hi = (z_tread, z_next) if z_next > z_tread else (z_next, z_tread)
                if along_x:
                    # Riser plane at x = p1, normal facing -X (back down an
                    # ascending run toward the start).
                    self.add_quad((p1, c0, lo), (p1, c0, hi),
                                  (p1, c1, hi), (p1, c1, lo),
                                  normal=(-1, 0, 0), material=wall_mat)
                else:
                    # Riser plane at y = p1, normal facing -Y.
                    self.add_quad((c0, p1, lo), (c1, p1, lo),
                                  (c1, p1, hi), (c0, p1, hi),
                                  normal=(0, -1, 0), material=wall_mat)

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def to_ter(self, name: str, version: int = 2) -> TerFile:
        """Emit a TerFile from the accumulated geometry."""
        ter = TerFile(name=name, magic=MAGIC_TERRAIN, version=version)
        ter.materials = list(self.materials)
        ter.vertices  = list(self.vertices)
        ter.polygons  = list(self.polygons)
        return ter


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------

def build_mesh(spec: ZoneSpec) -> MeshBuilder:
    """Build a complete MeshBuilder from a ZoneSpec."""
    mb = MeshBuilder()

    # Ensure every referenced material exists (fallback to a default grey)
    _ensure_materials(spec)

    for room in spec.rooms:
        mb.add_room(room, spec)
    for cor in spec.corridors:
        mb.add_corridor(cor, spec)

    return mb


def _door_openings(room: RoomSpec, spec: ZoneSpec
                   ) -> Dict[str, List[Tuple[float, float, float]]]:
    """Where each corridor attached to *room* passes through its walls.

    Returns {side: [(c0, c1, top), ...]}: the corridor's end leg spans c0..c1
    along that wall (its own width, centred on the leg's cross coordinate as
    `_add_straight_leg` builds it) and its ceiling meets the wall plane at
    `top`. The ceiling of a ramp or staircase is linear along the leg, so it is
    interpolated at the wall plane; a lintel from there up stays clear of it.
    Only sides listed in room.open_walls are reported.
    """
    rooms = {r.id: r for r in spec.rooms}
    (x0, y0, _), (x1, y1, _) = room.bounds
    out: Dict[str, List[Tuple[float, float, float]]] = {}
    for cor in spec.corridors:
        ends = []
        if cor.from_room == room.id:
            ends.append("from")
        if cor.to_room == room.id:
            ends.append("to")
        if not ends:
            continue
        route = corridor_route(cor, rooms)
        wps = list(route.waypoints)
        zs, _ = MeshBuilder._waypoint_zs(
            wps, None if route.carry < 0 else route.carry,
            cor.from_z, cor.to_z)
        hw = cor.width / 2
        for end in ends:
            k = 0 if end == "from" else len(wps) - 2
            along_x = route.axes[k]
            # The leg as built: its bend end stops at the bend square. When the
            # squares swallow the whole leg, the floor there is the bend's.
            built = MeshBuilder._leg_ends(wps, k, hw, zs)
            if built is None:
                zb_end = zs[k + 1] if end == "from" else zs[k]
                built, zs_k = (wps[k], wps[k + 1]), (zb_end, zb_end)
            else:
                zs_k = (zs[k], zs[k + 1])
            (ax, ay), (bx, by) = built
            ex, ey = wps[0] if end == "from" else wps[-1]
            if along_x:
                side = "E" if ex >= room.center_x else "W"
                plane, pa, pb, cross = (x1 if side == "E" else x0), ax, bx, ay
            else:
                side = "N" if ey >= room.center_y else "S"
                plane, pa, pb, cross = (y1 if side == "N" else y0), ay, by, ax
            if side not in room.open_walls:
                continue
            za, zb = zs_k
            if abs(pb - pa) > 1e-9:
                t = min(1.0, max(0.0, (plane - pa) / (pb - pa)))
            else:
                t = 0.0
            top = za + (zb - za) * t + cor.height
            out.setdefault(side, []).append((cross - hw, cross + hw, top))
    return out


def _merge_openings(openings, lo: float, hi: float
                    ) -> List[Tuple[float, float, float]]:
    """Clip openings to the wall's extent lo..hi and merge overlaps, sorted
    along the wall. A merged opening takes the higher top, so its lintel stays
    clear of every corridor ceiling it covers."""
    clipped = sorted((max(lo, c0), min(hi, c1), top)
                     for c0, c1, top in openings if min(hi, c1) > max(lo, c0))
    merged: List[Tuple[float, float, float]] = []
    for c0, c1, top in clipped:
        if merged and c0 <= merged[-1][1]:
            m0, m1, mt = merged[-1]
            merged[-1] = (m0, max(m1, c1), max(mt, top))
        else:
            merged.append((c0, c1, top))
    return merged


def _ensure_materials(spec: ZoneSpec) -> None:
    """Guarantee floor/wall/ceiling materials exist with sensible defaults."""
    defaults = {
        "floor":   ((100, 95, 90),  "worn stone flagstone floor"),
        "wall":    ((110, 105, 100),"rough hewn stone block wall"),
        "ceiling": ((70, 68, 65),   "dark rough rock ceiling"),
    }
    for name, (color, desc) in defaults.items():
        if name not in spec.materials:
            spec.add_material(name, f"{name}.dds", color=color, description=desc)
