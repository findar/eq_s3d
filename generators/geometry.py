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
        Build a corridor as a tube between two points.

        Corridors are axis-aligned (run along whichever of X/Y has the larger
        horizontal delta). If the two ends differ in height (from_z != to_z),
        the corridor ramps between them. If `steps` > 0, build a staircase.
        """
        floor_mat   = self.material_id(spec.materials[cor.floor_material])
        wall_mat    = self.material_id(spec.materials[cor.wall_material])
        ceiling_mat = self.material_id(spec.materials[cor.ceiling_material])

        hw = cor.width / 2
        dx = cor.to_x - cor.from_x
        dy = cor.to_y - cor.from_y
        along_x = abs(dx) >= abs(dy)

        # Normalise so we always build from the lower-coordinate end to the
        # higher-coordinate end, carrying the correct floor heights along.
        if along_x:
            if cor.from_x <= cor.to_x:
                a_pos, a_z, b_pos, b_z = cor.from_x, cor.from_z, cor.to_x, cor.to_z
            else:
                a_pos, a_z, b_pos, b_z = cor.to_x, cor.to_z, cor.from_x, cor.from_z
            cross = cor.from_y
            c0, c1 = cross - hw, cross + hw
        else:
            if cor.from_y <= cor.to_y:
                a_pos, a_z, b_pos, b_z = cor.from_y, cor.from_z, cor.to_y, cor.to_z
            else:
                a_pos, a_z, b_pos, b_z = cor.to_y, cor.to_z, cor.from_y, cor.from_z
            cross = cor.from_x
            c0, c1 = cross - hw, cross + hw

        if cor.steps > 0 and abs(b_z - a_z) > 0.01:
            self._add_stepped_corridor(a_pos, a_z, b_pos, b_z, c0, c1,
                                       cor.height, cor.steps, along_x,
                                       floor_mat, wall_mat, ceiling_mat)
        else:
            self._add_ramp_corridor(a_pos, a_z, b_pos, b_z, c0, c1,
                                    cor.height, along_x,
                                    floor_mat, wall_mat, ceiling_mat)

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
        Staircase: `steps` flat treads, each raised by one riser, with a
        vertical riser face between treads.
        """
        total_run = b_pos - a_pos
        total_rise = b_z - a_z
        run_per_step = total_run / steps
        rise_per_step = total_rise / steps

        for i in range(steps):
            p0 = a_pos + i * run_per_step
            p1 = a_pos + (i + 1) * run_per_step
            z_tread = a_z + (i + 1) * rise_per_step   # flat tread height
            zc0 = a_z + i * rise_per_step + height
            zc1 = a_z + (i + 1) * rise_per_step + height

            # Flat tread (floor + ceiling + side walls) at constant z_tread
            self._seg_quad(along_x, p0, p1, c0, c1,
                           z_tread, z_tread, zc0, zc1,
                           floor_mat, wall_mat, ceiling_mat)

            # Vertical riser face at the start of this step (from previous tread
            # height up to this tread height), facing back down the stairs.
            z_prev = a_z + i * rise_per_step
            if z_tread > z_prev:
                if along_x:
                    self.add_quad((p0, c0, z_prev), (p0, c1, z_prev),
                                  (p0, c1, z_tread), (p0, c0, z_tread),
                                  normal=(1, 0, 0), material=floor_mat)
                else:
                    self.add_quad((c0, p0, z_prev), (c0, p0, z_tread),
                                  (c1, p0, z_tread), (c1, p0, z_prev),
                                  normal=(0, 1, 0), material=floor_mat)

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
