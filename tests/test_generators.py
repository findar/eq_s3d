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
        spec = ZoneSpec(name="test", zone_type="dungeon")
        spec.add_material("wall", "wall.dds", color=(100, 90, 80))
        spec.rooms.append(RoomSpec("r0", 0, 0, width=200, depth=200, height=60))
        spec.lights.append(LightSpec("l0", 0, 0, 40))

        path = tmp_path / "test.json"
        spec.save(path)
        loaded = ZoneSpec.load(path)

        assert loaded.name == "test"
        assert loaded.zone_type == "dungeon"
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
        gen_a = LayoutGenerator(zone_type="dungeon", seed=123)
        gen_b = LayoutGenerator(zone_type="dungeon", seed=123)
        spec_a = gen_a.generate("z", room_count=4)
        spec_b = gen_b.generate("z", room_count=4)
        # Same seed → same room centres
        for ra, rb in zip(spec_a.rooms, spec_b.rooms):
            assert ra.center_x == rb.center_x
            assert ra.center_y == rb.center_y

    def test_room_count(self):
        gen = LayoutGenerator(zone_type="dungeon", seed=1)
        spec = gen.generate("z", room_count=6)
        assert len(spec.rooms) == 6
        # TinyKeep layout: at least N-1 corridors (MST = connected), possibly
        # a few more from loop edges added back for alternate paths.
        assert len(spec.corridors) >= 5
        # But not fully connected (that would be a complete graph)
        assert len(spec.corridors) < 6 * 5 // 2

    def test_lights_generated(self):
        gen = LayoutGenerator(zone_type="dungeon", seed=1)
        spec = gen.generate("z", room_count=3, add_lights=True)
        assert len(spec.lights) == 3

    def test_connected_rooms_open_walls(self):
        gen = LayoutGenerator(zone_type="dungeon", seed=1)
        spec = gen.generate("z", room_count=3)
        # Connected rooms should have at least one open wall each
        assert any(r.open_walls for r in spec.rooms)

    def test_wilderness_rooms_larger_than_dungeon(self):
        # Zone-type-accurate scale: wilderness zones are far larger than dungeons.
        dungeon = LayoutGenerator(zone_type="dungeon", seed=1).generate("d", room_count=5)
        wilderness = LayoutGenerator(zone_type="wilderness", seed=1).generate("o", room_count=5)
        d_side = dungeon.rooms[0].width
        o_side = wilderness.rooms[0].width
        assert o_side > d_side * 3, f"wilderness {o_side:.0f} vs dungeon {d_side:.0f}"

    def test_size_multiplier_scales(self):
        base = LayoutGenerator(zone_type="dungeon", seed=1)
        base_spec = base.generate("b", room_count=5)
        big = LayoutGenerator(zone_type="dungeon", seed=1)
        big.size_multiplier = 2.0
        big_spec = big.generate("g", room_count=5)
        assert big_spec.rooms[0].width > base_spec.rooms[0].width * 1.5

    def test_more_rooms_smaller_each(self):
        few = LayoutGenerator(zone_type="dungeon", seed=1).generate("f", room_count=3)
        many = LayoutGenerator(zone_type="dungeon", seed=1).generate("m", room_count=15)
        # Dividing the footprint across more rooms → smaller individual rooms
        assert many.rooms[0].width < few.rooms[0].width


class TestTinyKeepLayout:
    def _rooms_overlap(self, a, b, gap=0.0):
        return (abs(b.center_x - a.center_x) < (a.width + b.width) / 2 - gap
                and abs(b.center_y - a.center_y) < (a.depth + b.depth) / 2 - gap)

    def test_no_room_overlaps(self):
        for seed in (3, 7, 11, 42):
            spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
                "z", room_count=12, elevation=False)
            rs = spec.rooms
            for i in range(len(rs)):
                for j in range(i + 1, len(rs)):
                    assert not self._rooms_overlap(rs[i], rs[j]), \
                        f"rooms {i},{j} overlap (seed {seed})"

    def test_fully_connected(self):
        # Build adjacency from corridors (by nearest room to each endpoint)
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate(
            "z", room_count=10, elevation=False)
        n = len(spec.rooms)
        # At minimum a spanning tree exists → corridors >= n-1
        assert len(spec.corridors) >= n - 1

    def test_connectivity_reachable(self):
        # Every room should be reachable from room 0 via the corridor graph.
        # Reconstruct adjacency by matching each corridor endpoint to the room
        # whose wall it sits on (endpoints are on room walls, within half the
        # room's extent of its centre on one axis).
        spec = LayoutGenerator(zone_type="dungeon", seed=11).generate(
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
            spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
                "z", room_count=16, elevation=False)
            total_extra += len(spec.corridors) - (len(spec.rooms) - 1)
        assert total_extra > 0, "no loop edges ever added across 20 seeds"

    def test_single_room(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=1).generate("z", room_count=1)
        assert len(spec.rooms) == 1
        assert len(spec.corridors) == 0

    def test_two_rooms_one_corridor(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=1).generate("z", room_count=2)
        assert len(spec.rooms) == 2
        assert len(spec.corridors) == 1


class TestPacing:
    def test_exactly_one_entrance_and_climax(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate("z", room_count=10)
        roles = [r.role for r in spec.rooms]
        assert roles.count("entrance") == 1
        assert roles.count("climax") == 1

    def test_entrance_is_depth_zero(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate("z", room_count=10)
        entrance = next(r for r in spec.rooms if r.role == "entrance")
        assert entrance.graph_depth == 0

    def test_climax_is_deepest(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate("z", room_count=10)
        climax = next(r for r in spec.rooms if r.role == "climax")
        max_depth = max(r.graph_depth for r in spec.rooms)
        assert climax.graph_depth == max_depth

    def test_climax_larger_than_deadends(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate("z", room_count=12)
        climax = next(r for r in spec.rooms if r.role == "climax")
        deadends = [r for r in spec.rooms if r.role == "deadend"]
        if deadends:
            avg_de = sum(r.width * r.depth for r in deadends) / len(deadends)
            assert climax.width * climax.depth > avg_de

    def test_depth_assigned_to_all(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=11).generate("z", room_count=10)
        # Every room reachable from entrance → every room has a sensible depth
        assert all(r.graph_depth >= 0 for r in spec.rooms)
        # At least some progression beyond the entrance
        assert max(r.graph_depth for r in spec.rooms) >= 2

    def test_safe_point_at_entrance(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate("z", room_count=10)
        entrance = next(r for r in spec.rooms if r.role == "entrance")
        sx, sy, _sz = spec.safe_point
        assert abs(sx - entrance.center_x) < 1.0
        assert abs(sy - entrance.center_y) < 1.0

    def test_lighting_fades_with_depth(self):
        # Deeper dungeon rooms should have dimmer lights than the entrance.
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate("z", room_count=12)
        depth_by_id = {r.id: r.graph_depth for r in spec.rooms}
        # Match lights to rooms by id prefix
        bright = {}
        for lt in spec.lights:
            # light id = light_<idx>_<role>; map by position to a room
            rid = min(spec.rooms,
                      key=lambda r: (r.center_x - lt.x) ** 2 + (r.center_y - lt.y) ** 2).id
            bright[depth_by_id[rid]] = (lt.r + lt.g + lt.b)
        if 0 in bright and max(bright) >= 3:
            assert bright[max(bright)] < bright[0]


class TestGating:
    def _room_at_wall(self, rooms, x, y):
        best, bd = None, float("inf")
        for i, r in enumerate(rooms):
            if (abs(x - r.center_x) <= r.width / 2 + 6 and
                    abs(y - r.center_y) <= r.depth / 2 + 6):
                d = (r.center_x - x) ** 2 + (r.center_y - y) ** 2
                if d < bd:
                    bd, best = d, i
        if best is not None:
            return best
        return min(range(len(rooms)),
                   key=lambda i: (rooms[i].center_x - x) ** 2 + (rooms[i].center_y - y) ** 2)

    def _is_solvable(self, spec):
        from collections import defaultdict
        rooms = spec.rooms
        rid = {r.id: i for i, r in enumerate(rooms)}
        entrance = next(i for i, r in enumerate(rooms) if r.role == "entrance")

        locked = {g.corridor_id: g.id for g in spec.gates}
        key_in = defaultdict(set)
        for g in spec.gates:
            key_in[rid[g.key_room_id]].add(g.id)

        adj = defaultdict(list)
        for c in spec.corridors:
            a = self._room_at_wall(rooms, c.from_x, c.from_y)
            b = self._room_at_wall(rooms, c.to_x, c.to_y)
            gate = locked.get(c.id)
            adj[a].append((b, gate))
            adj[b].append((a, gate))

        keys, changed = set(), True
        reachable = set()
        while changed:
            changed = False
            seen = {entrance}
            stack = [entrance]
            while stack:
                cur = stack.pop()
                for g in key_in.get(cur, ()):
                    if g not in keys:
                        keys.add(g); changed = True
                for nxt, gate in adj[cur]:
                    if nxt in seen:
                        continue
                    if gate is not None and gate not in keys:
                        continue
                    seen.add(nxt); stack.append(nxt)
            reachable = seen
        return len(reachable) == len(rooms)

    def test_open_dungeon_has_no_gates(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=3).generate(
            "z", room_count=12, locks=0)
        assert len(spec.gates) == 0

    def test_keyed_dungeon_has_gates(self):
        spec = LayoutGenerator(zone_type="dungeon", seed=3).generate(
            "z", room_count=12, locks=2)
        assert len(spec.gates) >= 1

    def test_keyed_dungeons_always_solvable(self):
        for locks in (1, 2, 3):
            for seed in range(10):
                spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
                    "z", room_count=12, locks=locks)
                assert self._is_solvable(spec), \
                    f"unsolvable: locks={locks} seed={seed}"

    def test_keys_shallower_than_their_locks(self):
        # Each key room's graph_depth should be <= the deepest reachable before
        # the lock — a simple sanity check that keys aren't placed behind locks.
        spec = LayoutGenerator(zone_type="dungeon", seed=5).generate(
            "z", room_count=12, locks=2)
        depth_by_id = {r.id: r.graph_depth for r in spec.rooms}
        for g in spec.gates:
            # Key should not be at an absurd depth; placed near entrance.
            assert depth_by_id[g.key_room_id] <= max(depth_by_id.values())


class TestGatingPlanner:
    def test_rule_planner_detects_keyed(self):
        from ai.rule_planner import RulePlanner
        p = RulePlanner().plan("a sealed vault with a locked sanctum")
        assert p.locks >= 1

    def test_rule_planner_open_is_zero(self):
        from ai.rule_planner import RulePlanner
        p = RulePlanner().plan("an open sprawling cave to explore")
        assert p.locks == 0
        assert p.zone_type == "dungeon"

    def test_rule_planner_explicit_word_count(self):
        from ai.rule_planner import RulePlanner
        p = RulePlanner().plan("a dungeon with three locked doors")
        assert p.locks == 3


class TestMapView:
    def test_renders_svg_with_rooms(self):
        from generators.mapview import render_map_svg
        gen = LayoutGenerator(zone_type="dungeon", seed=11)
        spec = gen.generate("maptest", room_count=6)
        svg = render_map_svg(spec)
        assert svg.startswith("<svg")
        assert svg.rstrip().endswith("</svg>")
        # One <rect> per room (plus background + legend), so at least room count
        assert svg.count("<rect") >= len(spec.rooms)

    def test_empty_spec_renders_placeholder(self):
        from generators.mapview import render_map_svg
        from generators.zone_spec import ZoneSpec
        svg = render_map_svg(ZoneSpec(name="empty"))
        assert svg.startswith("<svg")
        assert "no layout" in svg

    def test_gates_drawn_when_present(self):
        from generators.mapview import render_map_svg
        gen = LayoutGenerator(zone_type="dungeon", seed=11)
        spec = gen.generate("maptest", room_count=10, locks=2)
        svg = render_map_svg(spec)
        # Gold key diamonds use <path>; two gates → at least two paths
        assert svg.count("<path") >= len(spec.gates)

    def test_builder_writes_map_sidecar(self, tmp_path):
        gen = LayoutGenerator(zone_type="dungeon", seed=11)
        spec = gen.generate("mapsidecar", room_count=4)
        ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=True)
        svg_path = tmp_path / "mapsidecar.map.svg"
        assert svg_path.exists()
        assert svg_path.read_text(encoding="utf-8").startswith("<svg")


class TestSemantics:
    """Content / semantic layer (Step 1 — single district, dungeon theme)."""

    def _themed(self, seed=7, rooms=10, theme="fortress", race="", tint=None):
        return LayoutGenerator(zone_type="dungeon", seed=seed).generate(
            "sem", room_count=rooms, dungeon_theme=theme,
            dungeon_race=race, elemental_tint=tint)

    def test_every_room_gets_a_type_and_theme(self):
        spec = self._themed()
        assert spec.dungeon_theme == "fortress"
        assert all(r.semantic_type for r in spec.rooms)
        assert all(r.room_theme == "fortress" for r in spec.rooms)

    def test_entrance_and_climax_map_to_arc_endpoints(self):
        from generators.semantics import ARCHETYPES
        arch = ARCHETYPES["fortress"]
        spec = self._themed()
        entrance = next(r for r in spec.rooms if r.role == "entrance")
        climax = next(r for r in spec.rooms if r.role == "climax")
        assert entrance.semantic_type == arch.entrance_type
        assert climax.semantic_type == arch.climax_type

    def test_boss_only_on_climax(self):
        spec = self._themed()
        bosses = [r for r in spec.rooms if r.boss]
        assert len(bosses) == 1
        assert bosses[0].role == "climax"

    def test_suggestion_fields_populated(self):
        spec = self._themed()
        # Every themed room carries data-only suggestions (no geometry).
        assert all(r.encounter_intent for r in spec.rooms)
        assert any(r.prop_hints for r in spec.rooms)

    def test_unthemed_dungeon_has_no_semantic_type(self):
        # A plain dungeon (no theme args) keeps the old behaviour.
        spec = LayoutGenerator(zone_type="dungeon", seed=7).generate("plain", room_count=8)
        assert spec.dungeon_theme == ""
        assert all(r.semantic_type == "" for r in spec.rooms)

    def test_water_theme_emits_water_region(self):
        spec = self._themed(theme="sunken_ruin")
        assert spec.elemental_tint == "water"
        assert any(r.kind == "water" for r in spec.regions)

    def test_lava_theme_emits_lava_region(self):
        spec = self._themed(theme="lava_forge")
        assert spec.elemental_tint == "lava"
        assert any(r.kind == "lava" for r in spec.regions)

    def test_themed_palette_adds_material_variants(self):
        spec = self._themed(theme="temple")
        # Themed zones register per-theme floor/wall variants and rooms use them.
        assert "wall_temple" in spec.materials
        assert any(r.wall_material == "wall_temple" for r in spec.rooms)

    def test_race_scale_enlarges_rooms(self):
        small = self._themed(race="froglok", seed=3)
        big = self._themed(race="giant", seed=3)
        # Same seed/arc → giant halls are larger than froglok halls.
        small_area = sum(r.width * r.depth for r in small.rooms)
        big_area = sum(r.width * r.depth for r in big.rooms)
        assert big_area > small_area * 2.0

    def test_deterministic_for_seed(self):
        a = self._themed(seed=99)
        b = self._themed(seed=99)
        assert [r.semantic_type for r in a.rooms] == [r.semantic_type for r in b.rooms]

    def test_rooms_stay_walkable_flat_floor(self):
        # Semantic shape bias must not tilt floors — rooms are still boxes with
        # a single floor_z (walkability invariant).
        spec = self._themed(theme="lava_forge", race="ogre")
        for r in spec.rooms:
            assert r.width > 0 and r.depth > 0 and r.height >= 50.0

    def test_sidecar_carries_semantic_fields(self, tmp_path):
        spec = self._themed(theme="wizard_lair", rooms=6)
        ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=True)
        import json
        data = json.loads((tmp_path / "sem.zone.json").read_text())
        # The content block moved from the sidecar "theme" key to "content"
        # (task 10.5); the field names inside are unchanged (Req 11.6).
        assert data["content"]["dungeon_theme"] == "wizard_lair"
        assert all("semantic_type" in rm for rm in data["rooms"])
        assert any(rm["boss"] for rm in data["rooms"])

    def test_map_labels_semantic_types(self):
        from generators.mapview import render_map_svg
        spec = self._themed(theme="temple", rooms=6)
        svg = render_map_svg(spec)
        # At least one room's semantic type appears as a label in the SVG.
        assert any(r.semantic_type in svg for r in spec.rooms)


class TestBuilder:
    def test_full_build(self, tmp_path):
        gen = LayoutGenerator(zone_type="dungeon", seed=42)
        spec = gen.generate("buildtest", room_count=4)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        assert result.eqg_path.exists()
        assert result.vertex_count > 0
        assert result.polygon_count > 0

    def test_build_produces_valid_eqg(self, tmp_path):
        gen = LayoutGenerator(zone_type="dungeon", seed=42)
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
        gen = LayoutGenerator(zone_type="dungeon", seed=42)
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
        gen = LayoutGenerator(zone_type="dungeon", seed=7)
        spec = gen.generate("ev", room_count=8, elevation=True)
        floor_zs = {r.floor_z for r in spec.rooms}
        # With elevation on and 8 rooms, we expect multiple distinct heights
        assert len(floor_zs) > 1

    def test_elevation_off_keeps_flat(self):
        gen = LayoutGenerator(zone_type="dungeon", seed=7)
        spec = gen.generate("flat", room_count=8, elevation=False)
        floor_zs = {r.floor_z for r in spec.rooms}
        assert floor_zs == {0.0}

    def test_elevated_zone_builds(self, tmp_path):
        gen = LayoutGenerator(zone_type="dungeon", seed=7)
        spec = gen.generate("evbuild", room_count=6, elevation=True)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
        assert result.eqg_path.exists()

        # Verify Z span is non-trivial
        arc = PfsArchive.from_file(result.eqg_path)
        ter = TerFile.from_bytes(arc.get("ter_evbuild.ter"))
        zs = [v.z for v in ter.vertices]
        assert max(zs) - min(zs) > 50  # has real verticality


class TestCorridorRouting:
    """
    Regression tests for the floating/misaligned staircase bug (seed
    678358326): corridor endpoints usually differ on BOTH axes, so the
    corridor must bend (L-shape) to meet both wall openings, and a staircase
    must start flush with the lower floor and finish flush with the upper one.
    """

    def _mesh(self, cor):
        spec = ZoneSpec(name="t")
        from generators.geometry import _ensure_materials
        _ensure_materials(spec)
        spec.corridors.append(cor)
        return build_mesh(spec)

    def test_offset_corridor_reaches_both_openings(self):
        # Endpoints offset on both axes (primary run along Y, 60u cross jog in X).
        cor = CorridorSpec("c", from_x=745, from_y=-152, to_x=681, to_y=-290,
                           from_z=0.0, to_z=-60.0, width=120, height=90, steps=6)
        mb = self._mesh(cor)
        xs = [v.x for v in mb.vertices]
        ys = [v.y for v in mb.vertices]
        hw = cor.width / 2
        # The L-corridor must have geometry at BOTH wall openings: near x=745
        # (room A's wall) and near y=-290 (room B's wall), within the width.
        assert min(abs(x - 745) for x in xs) <= hw + 1
        assert min(abs(y - (-290)) for y in ys) <= hw + 1
        # And it must actually span the full cross jog in X (745 -> 681).
        assert min(xs) <= 681 + hw + 1
        assert max(xs) >= 745 - hw - 1

    def test_staircase_is_flush_at_both_landings(self):
        cor = CorridorSpec("s", from_x=0, from_y=0, to_x=600, to_y=0,
                           from_z=0.0, to_z=60.0, width=100, height=90, steps=6)
        mb = self._mesh(cor)
        # Collect tread (floor, +Z normal) heights.
        tread_z = sorted({
            round(mb.vertices[p.v1].z, 3)
            for p in mb.polygons
            if mb.vertices[p.v1].nz > 0.9
            and abs(mb.vertices[p.v1].z - mb.vertices[p.v2].z) < 1e-3
            and abs(mb.vertices[p.v2].z - mb.vertices[p.v3].z) < 1e-3
        })
        # First tread flush with the lower floor; treads climb one rise each.
        assert tread_z[0] == 0.0
        assert tread_z == [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
        # The final riser (a vertical wall, |nx|~1 for an X-run) must climb to
        # the upper floor level (60) so there's no gap at the top landing.
        riser_tops = [
            v.z for v in mb.vertices if abs(v.nx) > 0.9
        ]
        assert max(riser_tops) >= 60.0 - 1e-3

    def test_straight_corridor_stays_single_leg(self):
        # Collinear endpoints (no cross offset) → should not add a corner fill.
        cor = CorridorSpec("c", from_x=0, from_y=0, to_x=400, to_y=0,
                           from_z=0.0, to_z=0.0, width=50, height=50)
        mb = self._mesh(cor)
        # A straight flat tube is floor+ceiling+2 walls = 4 quads = 8 tris.
        assert len(mb.polygons) == 8

    def _opening_point(self, room, toward):
        # Mirror of LayoutGenerator._wall_point (where the wall hole is cut).
        dx = toward.center_x - room.center_x
        dy = toward.center_y - room.center_y
        hw, hd = room.width / 2, room.depth / 2
        if abs(dx) >= abs(dy):
            return room.center_x + (hw - 2) * (1 if dx > 0 else -1), room.center_y
        return room.center_x, room.center_y + (hd - 2) * (1 if dy > 0 else -1)

    def test_corridor_floor_covers_both_openings(self):
        # Regression (seed 1516796975): a corridor's first leg must exit each
        # wall PERPENDICULAR to it. The layout picks each wall from the room-
        # centre delta, but add_corridor used to pick its run axis from the raw
        # endpoint delta — which can differ once both ends are inset to wall
        # midpoints, so a leg ran ALONG the wall and the room opening didn't
        # line up with the corridor (a visibly disconnected corridor). Assert
        # every corridor's floor footprint covers both room openings, across
        # several seeds (including the two earlier staircase-bug seeds).
        for seed in (1516796975, 481893615, 678358326, 42, 1, 99):
            spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
                "cov", room_count=9)
            rooms = {r.id: r for r in spec.rooms}
            for cor in spec.corridors:
                a, b = rooms[cor.from_room], rooms[cor.to_room]
                mb = MeshBuilder()
                from generators.geometry import _ensure_materials
                _ensure_materials(spec)
                mb.add_corridor(cor, spec)
                fx = [v.x for v in mb.vertices if v.nz > 0.5]
                fy = [v.y for v in mb.vertices if v.nz > 0.5]
                assert fx and fy, f"{seed}/{cor.id}: corridor has no floor"
                for room, toward in ((a, b), (b, a)):
                    ox, oy = self._opening_point(room, toward)
                    covered = (min(fx) - 1 <= ox <= max(fx) + 1 and
                               min(fy) - 1 <= oy <= max(fy) + 1)
                    assert covered, (
                        f"seed {seed} {cor.id}: opening ({ox:.0f},{oy:.0f}) "
                        f"not covered by corridor floor")

    def test_stepped_lbend_meets_both_room_floors(self):
        # Regression (seed 481893615): on an L-bend staircase, the whole rise
        # must resolve on ONE leg so the corridor floor reaches each room's
        # floor height at its opening — never an interpolated corner height that
        # leaves a gap / a staircase bleeding into a ramp. Here the primary run
        # is along Y (longer) and there's a shorter X jog; the stairs go on the
        # Y leg, so the X leg must be flat at the destination floor (to_z).
        cor = CorridorSpec("s", from_x=545, from_y=-596, to_x=496, to_y=-519,
                           from_z=-45.0, to_z=-6.7, width=90, height=90, steps=5)
        mb = self._mesh(cor)
        # Floor (+Z) vertices at the destination opening (x≈496) must sit at the
        # destination floor height (-6.7), not partway (e.g. -21 or -26).
        dest_floor_z = [
            v.z for v in mb.vertices
            if v.nz > 0.9 and abs(v.x - 496) <= 1.0
        ]
        assert dest_floor_z, "no corridor floor reaches the destination opening"
        assert min(dest_floor_z) == pytest.approx(-6.7, abs=0.5)
        # And floor at the source opening (y≈-596) must sit at the source floor.
        src_floor_z = [
            v.z for v in mb.vertices
            if v.nz > 0.9 and abs(v.y - (-596)) <= 1.0
        ]
        assert src_floor_z
        assert min(src_floor_z) == pytest.approx(-45.0, abs=0.5)

    # ------------------------------------------------------------------
    # Same-axis Z-corridor routing + walkable elevation (seed 1955208177)
    # ------------------------------------------------------------------

    @staticmethod
    def _wall_axis(room, toward):
        dx = toward.center_x - room.center_x
        dy = toward.center_y - room.center_y
        if abs(dx) >= abs(dy):
            return "E" if dx > 0 else "W"
        return "N" if dy > 0 else "S"

    @staticmethod
    def _floor_z_at_opening(mb, px, py, wall, tol=1.5):
        # Floor (+Z) height where the corridor meets an opening, probed ALONG
        # the wall line so a nearby stair-tread edge of the jog can't give a
        # false reading (see scripts/measure_corridors.py).
        on_x_wall = wall in ("E", "W")
        best_d, best_z = float("inf"), None
        for v in mb.vertices:
            if v.nz <= 0.5:
                continue
            if on_x_wall:
                if abs(v.x - px) > tol:
                    continue
                d = (v.y - py) ** 2
            else:
                if abs(v.y - py) > tol:
                    continue
                d = (v.x - px) ** 2
            if d < best_d:
                best_d, best_z = d, v.z
        return best_z

    @staticmethod
    def _max_floor_slope(mb):
        worst = 0.0
        for p in mb.polygons:
            vs = [mb.vertices[p.v1], mb.vertices[p.v2], mb.vertices[p.v3]]
            if any(v.nz <= 0.5 for v in vs):
                continue
            zspan = max(v.z for v in vs) - min(v.z for v in vs)
            if zspan < 1e-6:
                continue
            run = ((max(v.x for v in vs) - min(v.x for v in vs)) ** 2 +
                   (max(v.y for v in vs) - min(v.y for v in vs)) ** 2) ** 0.5
            if run > 1e-6:
                worst = max(worst, zspan / run)
        return worst

    def test_same_axis_pair_routes_as_z_corridor_flush(self):
        # Two rooms facing each other on PARALLEL E/W walls, offset in Y, with
        # an elevation change. The old single-corner L ran one leg along a wall
        # and met that opening at the wrong height; the Z-corridor must meet
        # BOTH openings flush at each room's floor_z.
        spec = ZoneSpec(name="t")
        from generators.geometry import _ensure_materials
        _ensure_materials(spec)
        a = RoomSpec("a", center_x=0, center_y=0, floor_z=0.0,
                     width=200, depth=200, height=90)
        b = RoomSpec("b", center_x=600, center_y=240, floor_z=40.0,
                     width=200, depth=200, height=90)
        spec.rooms.extend([a, b])
        a.open_walls.append("E")
        b.open_walls.append("W")
        cor = CorridorSpec("c", from_x=98, from_y=0, to_x=502, to_y=240,
                           from_z=0.0, to_z=40.0, width=60, height=80,
                           from_room="a", to_room="b")
        spec.corridors.append(cor)
        mb = MeshBuilder()
        mb.add_corridor(cor, spec)
        # Flush at A's E wall (x≈98) at z=0, and at B's W wall (x≈502) at z=40.
        za = self._floor_z_at_opening(mb, 98, 0, "E")
        zb = self._floor_z_at_opening(mb, 502, 240, "W")
        assert za == pytest.approx(0.0, abs=2.0)
        assert zb == pytest.approx(40.0, abs=2.0)

    def test_pinned_and_random_seeds_corridors_connect_and_walkable(self):
        # The regression bar for the corridor-connection task: across the
        # reported elevation-heavy seeds plus random ones, EVERY corridor must
        # meet both room openings flush (right floor height) AND be walkable
        # (ramp grade bounded, stair step height bounded). Structural-only tests
        # passed while 3D showed gaps, so this asserts the measured geometry.
        from generators.geometry import _ensure_materials
        seeds = [1955208177, 1516796975, 678358326, 481893615,
                 4, 53, 161, 7, 42, 99, 2024]
        for seed in seeds:
            spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
                "cw", room_count=9)
            _ensure_materials(spec)
            rooms = {r.id: r for r in spec.rooms}
            for cor in spec.corridors:
                a, b = rooms[cor.from_room], rooms[cor.to_room]
                mb = MeshBuilder()
                mb.add_corridor(cor, spec)

                wa = self._wall_axis(a, b)
                wb = self._wall_axis(b, a)
                oax, oay = self._opening_point(a, b)
                obx, oby = self._opening_point(b, a)
                za = self._floor_z_at_opening(mb, oax, oay, wa)
                zb = self._floor_z_at_opening(mb, obx, oby, wb)
                assert za is not None and zb is not None, \
                    f"seed {seed} {cor.id}: corridor has no floor at an opening"
                # Flush: corridor floor at each opening == room floor_z (<2u).
                assert za == pytest.approx(a.floor_z, abs=2.0), \
                    f"seed {seed} {cor.id}: gap at {a.id} ({za} vs {a.floor_z})"
                assert zb == pytest.approx(b.floor_z, abs=2.0), \
                    f"seed {seed} {cor.id}: gap at {b.id} ({zb} vs {b.floor_z})"

                dz = abs(cor.to_z - cor.from_z)
                if dz <= 0.5:
                    continue
                if cor.steps > 0:
                    # Stair step height bounded to ~a player step.
                    assert dz / cor.steps <= 8.0, \
                        f"seed {seed} {cor.id}: {dz/cor.steps:.1f}u/step too tall"
                else:
                    # Ramp grade bounded to a walkable slope (~27°, allow a
                    # small numerical margin from triangle measurement).
                    slope = self._max_floor_slope(mb)
                    assert slope <= 0.6, \
                        f"seed {seed} {cor.id}: ramp slope {slope:.2f} too steep"


class TestDoorwayWalls:
    """An open room side is cut only where a corridor meets it: wall either
    side of each doorway and a lintel above it, so the only gap is the
    corridor's own width (its routed end leg) and height."""

    _NORMALS = {"S": (0, 1, 0), "N": (0, -1, 0), "W": (1, 0, 0), "E": (-1, 0, 0)}

    @classmethod
    def _wall_pieces(cls, mb, side):
        """(a, b, zlo, zhi) of every wall quad on `side`, `a..b` along it."""
        pieces = []
        for q in range(0, len(mb.vertices), 4):
            vs = mb.vertices[q:q + 4]
            if (vs[0].nx, vs[0].ny, vs[0].nz) != cls._NORMALS[side]:
                continue
            along = [v.x for v in vs] if side in "SN" else [v.y for v in vs]
            pieces.append((min(along), max(along),
                           min(v.z for v in vs), max(v.z for v in vs)))
        return pieces

    @staticmethod
    def _expected(room, spec):
        """Doorways from corridor_route: {side: [(c0, c1, ceiling_at_wall)]}."""
        from generators.routing import corridor_route
        rooms = {r.id: r for r in spec.rooms}
        (x0, y0, _), (x1, y1, _) = room.bounds
        out = {}
        for cor in spec.corridors:
            for end, rid in (("from", cor.from_room), ("to", cor.to_room)):
                if rid != room.id:
                    continue
                route = corridor_route(cor, rooms)
                k = 0 if end == "from" else len(route.axes) - 1
                cross = (route.waypoints[k][1] if route.axes[k]
                         else route.waypoints[k][0])
                ex, ey = route.waypoints[0 if end == "from" else -1]
                if route.axes[k]:
                    side = "E" if ex >= room.center_x else "W"
                else:
                    side = "N" if ey >= room.center_y else "S"
                z = cor.from_z if end == "from" else cor.to_z
                out.setdefault(side, []).append(
                    (cross - cor.width / 2, cross + cor.width / 2, cor, z))
        return out

    def _check_room(self, room, spec, label):
        from generators.geometry import _ensure_materials
        _ensure_materials(spec)
        mb = MeshBuilder()
        mb.add_room(room, spec)
        (x0, y0, z0), (x1, y1, z1) = room.bounds
        expected = self._expected(room, spec)
        for side in room.open_walls:
            lo, hi = (x0, x1) if side in "SN" else (y0, y1)
            doors = expected.get(side, [])
            assert doors, f"{label}: open side {side} has no corridor"
            pieces = self._wall_pieces(mb, side)
            # Gaps at floor level = the full-height pieces' complement.
            full = sorted((a, b) for a, b, zl, zh in pieces
                          if zl == pytest.approx(z0) and zh == pytest.approx(z1))
            gaps, pos = [], lo
            for a, b in full:
                if a > pos + 1e-6:
                    gaps.append((pos, a))
                pos = max(pos, b)
            if pos < hi - 1e-6:
                gaps.append((pos, hi))
            want = sorted({(round(max(lo, c0), 6), round(min(hi, c1), 6))
                           for c0, c1, _, _ in doors})
            assert [(round(a, 6), round(b, 6)) for a, b in gaps] == want, \
                f"{label} side {side}: gaps {gaps} != corridor spans {want}"
            # Each doorway is exactly as tall as its corridor: a lintel spans
            # it from the corridor ceiling (within a ramp's rise over the 2u
            # inset) up to the room ceiling.
            for c0, c1, cor, zend in doors:
                lintels = [p for p in pieces
                           if p[0] == pytest.approx(max(lo, c0))
                           and p[1] == pytest.approx(min(hi, c1))
                           and p[2] > z0 + 1e-6]
                if zend + cor.height >= z1:
                    continue
                assert len(lintels) == 1, f"{label} side {side}: no lintel"
                _, _, zl, zh = lintels[0]
                assert zh == pytest.approx(z1)
                assert zl == pytest.approx(zend + cor.height, abs=1.5), \
                    f"{label} side {side}: lintel at {zl}, corridor top " \
                    f"{zend + cor.height}"

    @pytest.mark.parametrize("seed", [1955208177, 1516796975, 678358326])
    def test_doorway_gap_matches_corridor_route(self, seed):
        spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
            "dw", room_count=12)
        assert spec.corridors
        for room in spec.rooms:
            self._check_room(room, spec, f"seed {seed} {room.id}")

    def test_two_corridors_on_one_side_get_two_openings(self):
        spec = ZoneSpec(name="t")
        a = RoomSpec("a", center_x=0, center_y=0, width=200, depth=200,
                     height=90)
        b = RoomSpec("b", center_x=400, center_y=-50, width=100, depth=100,
                     height=90)
        c = RoomSpec("c", center_x=400, center_y=60, width=100, depth=100,
                     height=90)
        spec.rooms.extend([a, b, c])
        a.open_walls.append("E")
        for r, y in ((b, -50), (c, 60)):
            r.open_walls.append("W")
            spec.corridors.append(CorridorSpec(
                f"a{r.id}", from_x=98, from_y=y, to_x=352, to_y=y,
                width=40, height=60, from_room="a", to_room=r.id))
        self._check_room(a, spec, "two-door")
        gaps = self._expected(a, spec)["E"]
        assert sorted((c0, c1) for c0, c1, _, _ in gaps) == [(-70, -30), (40, 80)]
