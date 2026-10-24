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

        # Walls (inward-facing). Skip any listed in open_walls.
        # South wall (y=y0), normal +Y (facing into room)
        if "S" not in room.open_walls:
            self.add_quad(
                (x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0),
                normal=(0, 1, 0), material=wall_mat,
            )
        # North wall (y=y1), normal -Y
        if "N" not in room.open_walls:
            self.add_quad(
                (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (x0, y1, z0),
                normal=(0, -1, 0), material=wall_mat,
            )
        # West wall (x=x0), normal +X
        if "W" not in room.open_walls:
            self.add_quad(
                (x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0),
                normal=(1, 0, 0), material=wall_mat,
            )
        # East wall (x=x1), normal -X
        if "E" not in room.open_walls:
            self.add_quad(
                (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0),
                normal=(-1, 0, 0), material=wall_mat,
            )

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
        Corner fills join consecutive legs at their shared height.
        """
        n_legs = len(waypoints) - 1
        if carry is None:
            carry = max(range(n_legs), key=lambda k: self._seg_len(waypoints, k))

        # Floor height at each waypoint: from_z up to (and including) the start
        # of the carry leg, to_z from the end of the carry leg onward.
        zs = [from_z if i <= carry else to_z for i in range(len(waypoints))]

        for k in range(len(waypoints) - 1):
            (x0, y0), (x1, y1) = waypoints[k], waypoints[k + 1]
            leg_steps = steps if k == carry else 0
            self._add_straight_leg(
                x0, y0, zs[k], x1, y1, zs[k + 1],
                axes[k], hw, height, leg_steps,
                floor_mat, wall_mat, ceiling_mat)

        # Fill each interior corner flush with the shared floor height there.
        for i in range(1, len(waypoints) - 1):
            self._add_corner_fill(waypoints[i][0], waypoints[i][1], zs[i],
                                  hw, height, floor_mat, ceiling_mat)

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

    def _add_corner_fill(self, cx, cy, cz, hw, height,
                         floor_mat, ceiling_mat):
        """
        Fill the square where two perpendicular legs meet, so the floor and
        ceiling are continuous through the bend (no hole at the corner).
        """
        x0, x1 = cx - hw, cx + hw
        y0, y1 = cy - hw, cy + hw
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
