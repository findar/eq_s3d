"""Saved hand-offs (world-sockets task 6, P9; Req 5.1-5.3).

Every accepted build writes ``<name>.world.json``, ``<name>.attach.json`` and
``<name>.rooms.json`` into its build directory; each stage rerun from its hand-off gives the
same text; a file of another version is refused, named. One build per zone type, through the
pipeline with the gate off (the post-pass writes the hand-offs either way).
"""

from __future__ import annotations

import json

import pytest

from ai.expand import layout_engine, plan_to_spec
from ai.schema import ZonePlan
from generators import room_context, stages, world as world_mod
from generators.builder import ZoneBuilder
from generators.decor.stock import eq_path_from_env
from generators.pipeline import generate_validated

ZONE_TYPES = ("dungeon", "city", "wilderness", "outdoor_dungeon")
SEED = 3
NAMES = ("world", "attach", "rooms")


def _plan(zone_type: str) -> ZonePlan:
    plan = ZonePlan(name=f"ho_{zone_type}", zone_type=zone_type)
    plan.validate()             # resolves the default layout, as plan_to_spec does
    return plan


@pytest.fixture(scope="module")
def builds(tmp_path_factory):
    out = tmp_path_factory.mktemp("handoffs")
    done = {}
    for zt in ZONE_TYPES:
        vb = generate_validated(lambda s, zt=zt: plan_to_spec(_plan(zt), seed=s), zone_type=zt,
                                zone_id=f"z_{zt}", seed=SEED, output_dir=out, write_glb=False,
                                validate_enabled=False, failure_log=None)
        done[zt] = vb
    return done


def _files(vb):
    name = vb.spec.name.lower()
    return {k: vb.build_dir / f"{name}.{k}.json" for k in NAMES}


@pytest.mark.parametrize("zone_type", ZONE_TYPES)
def test_every_build_directory_holds_the_three_files(builds, zone_type):
    vb = builds[zone_type]
    files = _files(vb)
    assert all(p.is_file() for p in files.values()), sorted(p.name for p in vb.build_dir.iterdir())
    # The sidecar names each Socket and what attached to it.
    side = json.loads(vb.result.sidecar_path.read_text(encoding="utf-8"))
    world = world_mod.load(files["world"])
    assert [s["id"] for s in side["sockets"]] == [s.id for s in world.sockets]
    # A point Site Socket may have nothing attached (null); every other Socket has its own.
    assert all(s["attached"] is not None for s in side["sockets"] if s["kind"] != "site")


@pytest.mark.parametrize("zone_type", ZONE_TYPES)
def test_the_world_reruns_from_its_file(builds, zone_type):
    path = _files(builds[zone_type])["world"]
    text = path.read_text(encoding="utf-8")
    recipe = world_mod.load(path).recipe
    again = world_mod.world_for(recipe.pop("zone_type"), recipe.pop("seed"), **recipe)
    assert again.to_json() == text


@pytest.mark.parametrize("zone_type", ZONE_TYPES)
def test_the_attachments_rerun_from_the_world_file(builds, zone_type):
    """Each Attachment made again from the saved World (and, for the ground, the earlier
    Attachments' saved edits and Kept_Clear) and the plan's fields equals the file's."""
    vb = builds[zone_type]
    files = _files(vb)
    text = files["attach"].read_text(encoding="utf-8")
    saved = stages.load_attachments(files["attach"])
    assert stages.attachments_json(saved) == text
    world = world_mod.load(files["world"])
    plan = _plan(zone_type)
    again = []
    for a in saved:
        socket = world.socket(a.socket)
        if a.kind == "root":
            spec = plan_to_spec(plan, seed=a.seed)
            again.append(stages.build_attachments(spec, world)[0])
        elif a.kind == "hillside":
            fields = dict(name=plan.name, room_count=plan.room_count, verticality=plan.verticality,
                          locks=plan.locks, dungeon_theme=plan.dungeon_theme,
                          dungeon_race=plan.dungeon_race, elemental_tint=plan.elemental_tint or None)
            engine = layout_engine(plan.layout, plan.rule_set, plan.verticality, outdoor=True)
            att = stages.attach_rooms(world, socket, fields, a.seed, engine)
            # A grown layout's rooms are dressed afterwards in plan_to_spec (Scales, walls,
            # Features), which moves no room: the boxes match; the dressed layout is the file's.
            def boxes(rooms):
                return [[r[k] for k in ("id", "center_x", "center_y", "floor_z", "width", "depth")]
                        for r in rooms]
            assert boxes(att.to_dict()["layout"]["rooms"]) == boxes(a.layout["rooms"])
            att.layout = a.layout
            again.append(att)
        else:
            ground = stages.apply_edits(world, saved[:saved.index(a)])
            again.append(stages.attach_sites(ground, ground.socket(a.socket), a.seed, **a.controls))
    assert stages.attachments_json(again) == text


@pytest.mark.parametrize("zone_type", ZONE_TYPES)
def test_the_rooms_rerun_from_their_file(builds, zone_type):
    """The RoomContexts read back give the same text, and decor placed from them is the
    decor placed from the build's own (with the install; without it there are none)."""
    vb = builds[zone_type]
    path = _files(vb)["rooms"]
    text = path.read_text(encoding="utf-8")
    recipe, rooms = room_context.load(path)
    assert stages.rooms_json(recipe, rooms) == text
    assert [c.to_dict() for c in rooms] == [c.to_dict() for c in vb.result.rooms]
    if eq_path_from_env() is None:
        assert rooms == []
        return
    from generators.decor.placement import place
    assert rooms, "Decor normal with the install hands decor its rooms"
    for live, read in zip(vb.result.rooms, rooms):
        assert place(read, control=recipe["decor"], decor_seed=recipe["decor_seed"]).to_dict() \
            == place(live, control=recipe["decor"], decor_seed=recipe["decor_seed"]).to_dict()


def test_decor_none_hands_on_no_rooms(tmp_path):
    """Decor ``none`` builds no RoomContexts: ``rooms.json`` holds an empty list. A bare
    ZoneBuilder (a scratch attempt) writes no hand-off; the pipeline's post-pass does."""
    spec = plan_to_spec(ZonePlan(name="ho_none", zone_type="dungeon", decor="none"), seed=SEED)
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    assert result.rooms == []
    assert not list(tmp_path.glob("*.world.json"))
    files = result.handoffs()
    assert json.loads(files["ho_none.rooms.json"])["rooms"] == []


def test_another_version_is_refused_named(builds, tmp_path):
    files = _files(builds["outdoor_dungeon"])
    for kind, read in (("world", world_mod.load), ("attach", stages.load_attachments),
                       ("rooms", room_context.load)):
        doc = json.loads(files[kind].read_text(encoding="utf-8"))
        doc["version"] = 99
        bad = tmp_path / f"bad.{kind}.json"
        bad.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError) as e:
            read(bad)
        assert str(bad) in str(e.value) and "99" in str(e.value) and "1" in str(e.value)
