"""
tests/test_generators.py
------------------------
Tests for the Phase 2 procedural generators and the full build pipeline.
"""

import pytest
from pathlib import Path

from generators.zone_spec import ZoneSpec, RoomSpec, CorridorSpec, LightSpec, RegionSpec
from generators.geometry import build_mesh, MeshBuilder
from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder
from core.pfs import PfsArchive
from core.ter import TerFile
from core.zon import ZonFile


class TestZoneSpec:
    def test_roundtrip(self, tmp_path):
        spec = ZoneSpec(name="test", theme="dungeon")
        spec.add_material("wall", "wall.dds", color=(100, 90, 80))
        spec.rooms.append(RoomSpec("r0", 0, 0, width=200, depth=200, height=60))
        spec.lights.append(LightSpec("l0", 0, 0, 40))

        path = tmp_path / "test.json"
        spec.save(path)
        loaded = ZoneSpec.load(path)

        assert loaded.name == "test"
        assert loaded.theme == "dungeon"
        assert len(loaded.rooms) == 1
        assert len(loaded.lights) == 1
        assert loaded.materials["wall"].color == (100, 90, 80)

    def test_room_bounds(self):
        room = RoomSpec("r", center_x=100, center_y=50, floor_z=0,
                        width=200, depth=100, height=60)
        bmin, bmax = room.bounds
        assert bmin == (0, 0, 0)
        assert bmax == (200, 100, 60)


class TestGeometry:
    def test_single_room_mesh(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        spec.rooms.append(RoomSpec("r0", 0, 0, width=200, depth=200, height=60))

        mb = build_mesh(spec)
        # A closed box = 6 faces = 12 triangles = 24 vertices
        assert len(mb.polygons) == 12
        assert len(mb.vertices) == 24
        assert len(mb.materials) == 3

    def test_open_walls_reduce_faces(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        room = RoomSpec("r0", 0, 0, width=200, depth=200, height=60)
        room.open_walls = ["N", "S"]  # omit 2 walls
        spec.rooms.append(room)

        mb = build_mesh(spec)
        # 6 faces - 2 omitted = 4 faces = 8 triangles
        assert len(mb.polygons) == 8

    def test_ter_emission(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        spec.rooms.append(RoomSpec("r0", 0, 0, width=200, depth=200, height=60))

        ter = build_mesh(spec).to_ter("ter_t", version=2)
        assert isinstance(ter, TerFile)
        # TER should round-trip through binary
        ter2 = TerFile.from_bytes(ter.to_bytes(), "ter_t")
        assert len(ter2.vertices) == len(ter.vertices)
        assert len(ter2.polygons) == len(ter.polygons)


class TestLayout:
    def test_deterministic_seed(self):
        gen_a = LayoutGenerator(theme="dungeon", seed=123)
        gen_b = LayoutGenerator(theme="dungeon", seed=123)
        spec_a = gen_a.generate("z", room_count=4)
        spec_b = gen_b.generate("z", room_count=4)
        # Same seed → same room centres
        for ra, rb in zip(spec_a.rooms, spec_b.rooms):
            assert ra.center_x == rb.center_x
            assert ra.center_y == rb.center_y

    def test_room_count(self):
        gen = LayoutGenerator(theme="dungeon", seed=1)
        spec = gen.generate("z", room_count=6)
        assert len(spec.rooms) == 6
        # TinyKeep layout: at least N-1 corridors (MST = connected), possibly
        # a few more from loop edges added back for alternate paths.
        assert len(spec.corridors) >= 5
        # But not fully connected (that would be a complete graph)
        assert len(spec.corridors) < 6 * 5 // 2

    def test_lights_generated(self):
        gen = LayoutGenerator(theme="dungeon", seed=1)
        spec = gen.generate("z", room_count=3, add_lights=True)
        assert len(spec.lights) == 3

    def test_connected_rooms_open_walls(self):
        gen = LayoutGenerator(theme="dungeon", seed=1)
        spec = gen.generate("z", room_count=3)
        # Connected rooms should have at least one open wall each
        assert any(r.open_walls for r in spec.rooms)

    def test_outdoor_rooms_larger_than_dungeon(self):
        # Theme-accurate scale: outdoor zones are far larger than dungeons.
        dungeon = LayoutGenerator(theme="dungeon", seed=1).generate("d", room_count=5)
        outdoor = LayoutGenerator(theme="outdoor", seed=1).generate("o", room_count=5)
        d_side = dungeon.rooms[0].width
        o_side = outdoor.rooms[0].width
        assert o_side > d_side * 3, f"outdoor {o_side:.0f} vs dungeon {d_side:.0f}"

    def test_size_multiplier_scales(self):
        base = LayoutGenerator(theme="dungeon", seed=1)
        base_spec = base.generate("b", room_count=5)
        big = LayoutGenerator(theme="dungeon", seed=1)
        big.size_multiplier = 2.0
        big_spec = big.generate("g", room_count=5)
        assert big_spec.rooms[0].width > base_spec.rooms[0].width * 1.5

    def test_more_rooms_smaller_each(self):
        few = LayoutGenerator(theme="dungeon", seed=1).generate("f", room_count=3)
        many = LayoutGenerator(theme="dungeon", seed=1).generate("m", room_count=15)
        # Dividing the footprint across more rooms → smaller individual rooms
        assert many.rooms[0].width < few.rooms[0].width


class TestTinyKeepLayout:
    def _rooms_overlap(self, a, b, gap=0.0):
        return (abs(b.center_x - a.center_x) < (a.width + b.width) / 2 - gap
                and abs(b.center_y - a.center_y) < (a.depth + b.depth) / 2 - gap)

    def test_no_room_overlaps(self):
        for seed in (3, 7, 11, 42):
            spec = LayoutGenerator(theme="dungeon", seed=seed).generate(
                "z", room_count=12, elevation=False)
            rs = spec.rooms
            for i in range(len(rs)):
                for j in range(i + 1, len(rs)):
                    assert not self._rooms_overlap(rs[i], rs[j]), \
                        f"rooms {i},{j} overlap (seed {seed})"

    def test_fully_connected(self):
        # Build adjacency from corridors (by nearest room to each endpoint)
        spec = LayoutGenerator(theme="dungeon", seed=7).generate(
            "z", room_count=10, elevation=False)
        n = len(spec.rooms)
        # At minimum a spanning tree exists → corridors >= n-1
        assert len(spec.corridors) >= n - 1

    def test_connectivity_reachable(self):
        # Every room should be reachable from room 0 via the corridor graph.
        # Reconstruct adjacency by matching each corridor endpoint to the room
        # whose wall it sits on (endpoints are on room walls, within half the
        # room's extent of its centre on one axis).
        spec = LayoutGenerator(theme="dungeon", seed=11).generate(
            "z", room_count=10, elevation=False)
        rooms = spec.rooms

        def room_at_wall(x, y):
            best, bd = None, float("inf")
            for idx, r in enumerate(rooms):
                # Point must be within the room's AABB (plus a small inset
                # tolerance since the wall point sits just inside the wall).
                within_x = abs(x - r.center_x) <= r.width / 2 + 5
                within_y = abs(y - r.center_y) <= r.depth / 2 + 5
                if within_x and within_y:
                    d = (r.center_x - x) ** 2 + (r.center_y - y) ** 2
                    if d < bd:
                        bd, best = d, idx
            return best

        adj = {i: set() for i in range(len(rooms))}
        for c in spec.corridors:
            a = room_at_wall(c.from_x, c.from_y)
            b = room_at_wall(c.to_x, c.to_y)
            if a is not None and b is not None and a != b:
                adj[a].add(b)
                adj[b].add(a)

        seen = {0}
        stack = [0]
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        assert len(seen) == len(rooms), \
            f"only {len(seen)}/{len(rooms)} rooms reachable"

    def test_loops_added_for_larger_zones(self):
        # A larger zone should get at least one loop edge above the MST (n-1).
        total_extra = 0
        for seed in range(20):
            spec = LayoutGenerator(theme="dungeon", seed=seed).generate(
                "z", room_count=16, elevation=False)
            total_extra += len(spec.corridors) - (len(spec.rooms) - 1)
        assert total_extra > 0, "no loop edges ever added across 20 seeds"

    def test_single_room(self):
        spec = LayoutGenerator(theme="dungeon", seed=1).generate("z", room_count=1)
        assert len(spec.rooms) == 1
        assert len(spec.corridors) == 0

    def test_two_rooms_one_corridor(self):
        spec = LayoutGenerator(theme="dungeon", seed=1).generate("z", room_count=2)
        assert len(spec.rooms) == 2
        assert len(spec.corridors) == 1


class TestBuilder:
    def test_full_build(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=42)
        spec = gen.generate("buildtest", room_count=4)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        assert result.eqg_path.exists()
        assert result.vertex_count > 0
        assert result.polygon_count > 0

    def test_build_produces_valid_eqg(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=42)
        spec = gen.generate("validtest", room_count=3)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        # Read the generated EQG back
        arc = PfsArchive.from_file(result.eqg_path)
        files = arc.list_files()

        assert "ter_validtest.ter" in [f.lower() for f in files]
        assert "validtest.zon" in [f.lower() for f in files]

        # TER parses
        ter_data = arc.get("ter_validtest.ter")
        ter = TerFile.from_bytes(ter_data)
        assert len(ter.vertices) > 0

        # ZON parses and references the terrain as model[0]
        zon_data = arc.get("validtest.zon")
        zon = ZonFile.from_bytes(zon_data)
        assert len(zon.models) >= 1
        assert "TER_VALIDTEST" in zon.models[0].upper()

    def test_zon_has_lights(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=42)
        spec = gen.generate("lighttest", room_count=3)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        arc = PfsArchive.from_file(result.eqg_path)
        zon = ZonFile.from_bytes(arc.get("lighttest.zon"))
        assert len(zon.lights) == 3


class TestElevation:
    def test_corridor_floor_z_backcompat(self):
        # The floor_z property sets both from_z and to_z
        c = CorridorSpec("c", 0, 0, 100, 0)
        c.floor_z = 50.0
        assert c.from_z == 50.0
        assert c.to_z == 50.0
        assert c.floor_z == 50.0

    def test_ramp_corridor_spans_heights(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        # A corridor that ramps from z=0 to z=100 along X
        spec.corridors.append(CorridorSpec(
            "ramp", from_x=0, from_y=0, to_x=400, to_y=0,
            from_z=0.0, to_z=100.0, width=50, height=50,
        ))
        mb = build_mesh(spec)
        ter = mb.to_ter("t")
        zs = [v.z for v in ter.vertices]
        # Floor should span from 0 up to 100; ceiling adds height on top
        assert min(zs) == 0.0
        assert max(zs) >= 100.0

    def test_stepped_corridor_more_geometry(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        spec.corridors.append(CorridorSpec(
            "stairs", from_x=0, from_y=0, to_x=400, to_y=0,
            from_z=0.0, to_z=100.0, width=50, height=50, steps=5,
        ))
        mb = build_mesh(spec)
        # Stepped corridors produce more polygons than a flat tube (treads + risers)
        assert len(mb.polygons) > 8

    def test_elevation_layout_varies_z(self):
        gen = LayoutGenerator(theme="dungeon", seed=7)
        spec = gen.generate("ev", room_count=8, elevation=True)
        floor_zs = {r.floor_z for r in spec.rooms}
        # With elevation on and 8 rooms, we expect multiple distinct heights
        assert len(floor_zs) > 1

    def test_elevation_off_keeps_flat(self):
        gen = LayoutGenerator(theme="dungeon", seed=7)
        spec = gen.generate("flat", room_count=8, elevation=False)
        floor_zs = {r.floor_z for r in spec.rooms}
        assert floor_zs == {0.0}

    def test_elevated_zone_builds(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=7)
        spec = gen.generate("evbuild", room_count=6, elevation=True)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
        assert result.eqg_path.exists()

        # Verify Z span is non-trivial
        arc = PfsArchive.from_file(result.eqg_path)
        ter = TerFile.from_bytes(arc.get("ter_evbuild.ter"))
        zs = [v.z for v in ter.vertices]
        assert max(zs) - min(zs) > 50  # has real verticality
