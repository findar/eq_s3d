"""Hallways match their rooms (interesting textures spec task 9, from the
task 8 first look: "i would expect hallways to match an adjacent room").

In a themed dungeon every corridor's floor and wall use the theme material of
a room it joins, every room (crossing waypoints included) is themed, and no
unused shared floor or wall texture is packed. Unthemed dungeons and cities
keep the shared materials throughout.
"""

import pytest

from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import ZoneBuilder

THEMED = [("a gnoll temple dungeon with 8 rooms", 7),
          ("a kobold tomb full of lava with 6 rooms", 11),
          ("a temple dungeon with 6 rooms", 5),
          ("an ogre fortress with 20 rooms", 3)]


@pytest.mark.parametrize("prompt, seed", THEMED)
def test_corridors_take_their_rooms_theme_material(prompt, seed):
    spec = plan_to_spec(make_plan(prompt, name="halls"), seed=seed)
    rooms = {r.id: r for r in spec.rooms}
    floors = {r.floor_material for r in spec.rooms}
    assert len(floors) == 1 and not next(iter(floors)).endswith("_dungeon_floor") \
        and next(iter(floors)) != "dungeon_floor"
    for cor in spec.corridors:
        ends = [rooms[i] for i in (cor.from_room, cor.to_room) if i in rooms]
        assert any(cor.floor_material == r.floor_material and
                   cor.wall_material == r.wall_material for r in ends), cor.id


@pytest.mark.parametrize("prompt, seed", THEMED[:2])
def test_no_unused_shared_floor_or_wall_is_packed(tmp_path, prompt, seed):
    spec = plan_to_spec(make_plan(prompt, name="halls"), seed=seed)
    r = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    arc = PfsArchive.from_file(r.eqg_path)
    ter = TerFile.from_bytes(arc.get("ter_halls.ter"))
    used = {m.name for m in ter.materials}
    packed = {n[:-4] for n in arc.list_files() if n.endswith(".dds")}
    assert packed == used
    assert not any(n.endswith(("_dungeon_floor", "_dungeon_wall")) for n in used)


@pytest.mark.parametrize("kind", ["dungeon", "city"])
def test_unthemed_builds_keep_the_shared_materials(kind):
    spec = plan_to_spec(ZonePlan(name="halls", zone_type=kind, walls="built"), seed=7)
    want = {f"{kind}_floor", f"{kind}_wall", f"{kind}_ceiling"}
    assert set(spec.materials) == want
    for part in (*spec.rooms, *spec.corridors):
        assert {part.floor_material, part.wall_material, part.ceiling_material} <= want
