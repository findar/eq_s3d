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

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.ter import TerFile, Material, Vertex, Polygon, MAGIC_TERRAIN
from .zone_spec import ZoneSpec, RoomSpec, CorridorSpec, MaterialSpec


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
        Build a corridor between two wall openings.

        The two endpoints usually differ on BOTH axes (the rooms are offset),
        so a single axis-aligned tube would miss one of the wall openings and
        leave the corridor — and any staircase on it — floating away from the
        wall. To meet both openings squarely we build an **L-shaped** corridor
        when the ends aren't (near) collinear: a straight leg out of the first
        wall, a corner, then a straight leg into the second wall. When the ends
        ARE collinear on an axis, we build a single straight leg as before.

        Height change (ramp or staircase) is applied to the longer leg; the
        shorter leg stays flat, so stairs sit on a real sloped run.
        """
        floor_mat   = self.material_id(spec.materials[cor.floor_material])
        wall_mat    = self.material_id(spec.materials[cor.wall_material])
        ceiling_mat = self.material_id(spec.materials[cor.ceiling_material])

        hw = cor.width / 2
        dx = cor.to_x - cor.from_x
        dy = cor.to_y - cor.from_y

        # The rooms open on whichever axis has the larger separation (the same
        # test layout uses to pick the facing wall). That axis is the "primary"
        # run direction out of both wall openings.
        primary_x = abs(dx) >= abs(dy)
        cross_off = abs(dy) if primary_x else abs(dx)

        # Near-collinear: a straight corridor meets both openings. (Allow a
        # little slack so tiny offsets don't force an unnecessary bend.)
        if cross_off <= max(2.0, hw * 0.5):
            self._add_straight_leg(
                cor.from_x, cor.from_y, cor.from_z,
                cor.to_x, cor.to_y, cor.to_z,
                primary_x, hw, cor.height, cor.steps,
                floor_mat, wall_mat, ceiling_mat)
            return

        # L-shaped: run out of the first wall along the primary axis to a corner
        # aligned under/over the second opening, then turn and run into the
        # second wall along the cross axis.
        if primary_x:
            corner_x, corner_y = cor.to_x, cor.from_y
        else:
            corner_x, corner_y = cor.from_x, cor.to_y

        # Split the height change across the two legs by run length so the
        # average grade is gentle; put the staircase (if any) on the longer leg.
        len1 = abs((corner_x - cor.from_x) if primary_x else (corner_y - cor.from_y))
        len2 = abs((cor.to_y - corner_y) if primary_x else (cor.to_x - corner_x))
        total = max(len1 + len2, 1e-6)
        corner_z = cor.from_z + (cor.to_z - cor.from_z) * (len1 / total)

        steps1 = cor.steps if (cor.steps and len1 >= len2) else 0
        steps2 = cor.steps if (cor.steps and len2 > len1) else 0

        # Leg 1: primary axis, from the first opening to the corner.
        self._add_straight_leg(
            cor.from_x, cor.from_y, cor.from_z,
            corner_x, corner_y, corner_z,
            primary_x, hw, cor.height, steps1,
            floor_mat, wall_mat, ceiling_mat)
        # Leg 2: cross axis, from the corner into the second opening.
        self._add_straight_leg(
            corner_x, corner_y, corner_z,
            cor.to_x, cor.to_y, cor.to_z,
            not primary_x, hw, cor.height, steps2,
            floor_mat, wall_mat, ceiling_mat)
        # Fill the inside/outside corner so the two legs join without a gap.
        self._add_corner_fill(corner_x, corner_y, corner_z, hw, cor.height,
                              floor_mat, ceiling_mat)

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
        """Single sloped segment from (a_pos,a_z) to (b_pos,b_z)."""
        self._seg_quad(along_x, a_pos, b_pos, c0, c1,
                       a_z, b_z, a_z + height, b_z + height,
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
