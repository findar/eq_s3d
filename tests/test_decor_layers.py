"""Decor rules task 1 (Reqs 1, 2.1; design "Decor layers"): decor layers merged onto rooms.toml.

Every layer here is a small file written in ``tmp_path``, onto a copy of the shipped base, but
the shipped tomb layer (task 3, Req 3.1), the worked example: base + tomb is the rules as they were
before it moved out of rooms.toml.
"""

import dataclasses
import re
import shutil
import tomllib
from collections.abc import Mapping

import pytest

from generators.decor.rules import (DECOR_DIR, LAYERS_DIR, ROOMS_FILE, SETS_FILE, THEMES_FILE, Group, Line, Member,
                                    Recipe, asks, layer_names, layers_for, load_decor, load_decor_themes)
from generators.topology.ruleset import RuleSetError

HEAD = '[layer]\nname = "{name}"\ndescription = "{desc}"\n'


def _folder(tmp_path):
    d = tmp_path / "decor"
    if not d.exists():
        (d / LAYERS_DIR).mkdir(parents=True)
        for f in (ROOMS_FILE, SETS_FILE):
            shutil.copy(DECOR_DIR / f, d / f)
    return d


def _layer(d, name, body="", desc="a test layer", head=True):
    """A layer file; top-level keys in ``body`` (``once = [...]``, before any table) go above the header."""
    top = re.match(r"(?:[^\[\n][^\n]*\n)*", body).group(0)
    text = top + (HEAD.format(name=name, desc=desc) if head else "") + body[len(top):]
    (d / LAYERS_DIR / f"{name}.toml").write_text(text, encoding="utf-8")


def _errors(d, layers):
    with pytest.raises(RuleSetError) as exc:
        load_decor(d, layers=layers)
    return exc.value.errors


def _where(errs):
    return [(e.file, e.where, e.field) for e in errs]


@pytest.fixture(scope="module")
def base():
    return load_decor()


# --- no layers: today's rules --------------------------------------------------------------------


def test_no_layers_and_an_empty_layer_change_nothing(tmp_path, base):
    assert load_decor(layers=()) == base and base.layers == ()
    d = _folder(tmp_path)
    _layer(d, "empty")
    got = load_decor(d, layers=["empty"])
    assert got.layers == ("empty",)
    for f in dataclasses.fields(base):
        if f.name != "layers":
            assert getattr(got, f.name) == getattr(base, f.name), f.name
    assert {line.where[0] for line in base.lines()} == {ROOMS_FILE}


# --- merge --------------------------------------------------------------------------------------------


def test_new_entries_are_added_and_named_by_their_file(tmp_path, base):
    d = _folder(tmp_path)
    _layer(d, "bones", '[groups.bone_heap]\nmembers = [ { kind = "skull", at = "anchor" }, '
                       '{ kind = "bones", at = "round", count = [1, 3] } ]\n'
                       '[weights.kinds.deep]\nlight = 0.5\n'
                       '[weights.types.barracks]\ndebris = 2\n')
    r = load_decor(d, layers=["bones"])
    assert [m.kinds for m in r.groups["bone_heap"].members] == [("skull",), ("bones",)]
    assert r.weights["kinds"]["deep"].weights == {"light": (0.5,)}
    assert r.weights_for("dungeon", room_type="barracks")["debris"] == pytest.approx(2 ** 0.5)
    got = {w: k for w, k, _ in asks(r) if w[1] == "groups.bone_heap"}
    assert set(got) == {("bones.toml", "groups.bone_heap", "members[0]"),
                        ("bones.toml", "groups.bone_heap", "members[1]")}
    # Nothing else moved.
    assert r.types == base.types and r.every == base.every


def test_an_entry_already_there_is_refused_naming_both_files(tmp_path):
    d = _folder(tmp_path)
    _layer(d, "a", '[types.barracks]\nprops = [ { kind = "skull", at = "scatter" } ]\n'
                   '[weights.themes.temple]\nlight = 0.2\n'
                   '[groups.bunks]\nmembers = [ { kind = "bed", at = "anchor" } ]\n'
                   '[dressing.boss]\nprops = [ { kind = "skull", at = "round" } ]\n')
    errs = _errors(d, ["a"])
    assert set(_where(errs)) == {("a.toml", "types.barracks", "mode"), ("a.toml", "weights.themes.temple", "mode"),
                                 ("a.toml", "groups.bunks", "mode"), ("a.toml", "dressing.boss", "mode")}
    assert all(ROOMS_FILE in e.expected for e in errs)
    # Between layers: the second names the first.
    _layer(d, "a", '[types.ossuary]\nmode = "replace"\nprops = [ { kind = "skull", at = "scatter" } ]\n')
    _layer(d, "b", '[types.ossuary]\nprops = [ { kind = "bones", at = "scatter" } ]\n')
    errs = _errors(d, ["a", "b"])
    assert _where(errs) == [("b.toml", "types.ossuary", "mode")] and "a.toml" in errs[0].expected


def test_mode_add_appends_lines_and_mode_replace_stands_instead(tmp_path, base):
    d = _folder(tmp_path)
    _layer(d, "x", '[types.barracks]\nmode = "add"\nprops = [ { kind = "skull", at = "scatter", count = [1, 2] } ]\n'
                   '[every]\nmode = "replace"\nprops = [ { kind = "torch", at = "on_wall" } ]\n'
                   '[groups.bunks]\nmode = "add"\nmembers = [ { kind = "chest", at = "beside" } ]\n')
    r = load_decor(d, layers=["x"])
    old = base.types["barracks"].lines
    assert r.types["barracks"].lines[:len(old)] == old
    added = r.types["barracks"].lines[len(old):]
    assert [(l.kinds, l.where) for l in added] == [(("skull",), ("x.toml", "types.barracks", "props[0]"))]
    assert [(l.kinds, l.where) for l in r.every.lines] == [(("torch",), ("x.toml", "every", "props[0]"))]
    members = r.groups["bunks"].members
    assert [m.kinds for m in members] == [("bed",), ("bed",), ("chest",)]
    assert [w for w, _, _ in asks(r) if w[1] == "groups.bunks"] == [
        (ROOMS_FILE, "groups.bunks", "members[0]"), (ROOMS_FILE, "groups.bunks", "members[1]"),
        ("x.toml", "groups.bunks", "members[0]")]


def test_layers_merge_in_the_order_given(tmp_path, base):
    d = _folder(tmp_path)
    _layer(d, "a", '[every]\nmode = "add"\nprops = [ { kind = "skull", at = "scatter" } ]\n')
    _layer(d, "b", '[every]\nmode = "add"\nprops = [ { kind = "bones", at = "scatter" } ]\n')
    n = len(base.every.lines)
    ab = load_decor(d, layers=["a", "b", "a"])
    ba = load_decor(d, layers=["b", "a"])
    assert ab.layers == ("a", "b") and ba.layers == ("b", "a")
    assert [l.kinds for l in ab.every.lines[n:]] == [("skull",), ("bones",)]
    assert [l.kinds for l in ba.every.lines[n:]] == [("bones",), ("skull",)]


def test_weights_add_joins_categories_and_refuses_a_clash(tmp_path, base):
    d = _folder(tmp_path)
    _layer(d, "w", '[weights.themes.temple]\nmode = "add"\ncontainer = 0.5\n')
    r = load_decor(d, layers=["w"])
    assert r.weights["themes"]["temple"].weights == {**base.weights["themes"]["temple"].weights, "container": (0.5,)}
    _layer(d, "w", '[weights.themes.temple]\nmode = "add"\ncontainer = 0.5\nlight = 0.3\n')
    errs = _errors(d, ["w"])
    assert _where(errs) == [("w.toml", "weights.themes.temple", "light")] and ROOMS_FILE in errs[0].expected
    # A Category one layer added clashes with the next, which names it.
    _layer(d, "w", '[weights.themes.temple]\nmode = "add"\ncontainer = 0.5\n')
    _layer(d, "v", '[weights.themes.temple]\nmode = "add"\ncontainer = 0.7\n')
    errs = _errors(d, ["w", "v"])
    assert _where(errs) == [("v.toml", "weights.themes.temple", "container")] and "w.toml" in errs[0].expected
    _layer(d, "w", '[weights.themes.temple]\nmode = "replace"\nlight = 0.3\n')
    assert load_decor(d, layers=["w"]).weights["themes"]["temple"].weights == {"light": (0.3,)}
    _layer(d, "w", '[weights.controls.normal]\nmode = "add"\nhanging = 2\n')
    assert load_decor(d, layers=["w"]).controls["normal"] == {"hanging": 2.0}


def test_a_layers_own_weights_reach_every_room_of_its_build_but_not_sites(tmp_path, base):
    """``[weights.layer]`` stands after the theme's entry for any room or corridor of a build
    that takes the layer, whatever its theme; a Site keeps its biome's look. Only a layer file
    writes one, and it takes no ``mode``."""
    d = _folder(tmp_path)
    _layer(d, "dim", "[weights.layer]\nlight = 0.25\n")
    r = load_decor(d, layers=["dim"])
    for theme in ("temple", "tomb", ""):
        room = dict(zone_type="dungeon", theme=theme, kind="chamber", room_type="shrine")
        own = r.weights["layers"]["dim"]
        got = r.layers_for(**room)
        assert own in got and tuple(x for x in got if x is not own) == base.layers_for(**room)
        assert r.weights_for(**room)["light"] < base.weights_for(**room)["light"]
        assert r.weights_for(**room, source="corridor") == r.weights_for(**room)
    site = dict(zone_type="outdoor_dungeon", race="orc", theme="plains", room_type="camp", source="site")
    assert r.weights_for(**site) == base.weights_for(**site)
    _layer(d, "dim", '[weights.layer]\nmode = "add"\nlight = 0.25\n')
    assert _where(_errors(d, ["dim"])) == [("dim.toml", "weights.layer", "mode")]
    rooms = (d / ROOMS_FILE).read_text(encoding="utf-8") + "\n[weights.layers.dim]\nlight = 0.25\n"
    (d / ROOMS_FILE).write_text(rooms, encoding="utf-8")
    assert _where(_errors(d, []))[0][:2] == (ROOMS_FILE, "weights")


def test_once_kinds_join_the_bases(tmp_path, base):
    d = _folder(tmp_path)
    _layer(d, "o", 'once = ["throne", "forge"]\n')
    assert load_decor(d, layers=["o"]).once == base.once | {"throne"}


# --- each layer checked on its own, the merged set as a whole -----------------------------------------


@pytest.mark.parametrize("body, where, fld", [
    ('[types.ossuary]\nmode = "add"\nprops = [ { kind = "skul", at = "scatter" } ]\n', "types.ossuary",
     "props[0].kind"),
    ('[types.ossuary]\nmode = "add"\nprops = [ { kind = "skull", at = "up" } ]\n', "types.ossuary", "props[0].at"),
    ('[types.ossuary]\nmode = "merge"\nprops = []\n', "types.ossuary", "mode"),
    ('[types.boneyard]\nprops = []\n', "types", "boneyard"),
    ('[dressing.lurk]\nprops = []\n', "dressing", "lurk"),
    ('[default]\nprops = []\n', "top level", "default"),
    ('[weights.themes.crypt]\nlight = 1\n', "weights.themes", "crypt"),
    ('[weights.kinds.deep]\nlamps = 1\n', "weights.kinds.deep", "lamps"),
    ('[weights.kinds.deep]\nlight = -1\n', "weights.kinds.deep", "light"),
    ('[weights.controls.dense]\nmode = "add"\nhanging = { value = 2, override = true }\n',
     "weights.controls.dense", "override"),
    ('[groups.bunks]\nmode = "add"\nmembers = [ { kind = "bed", at = "anchor" } ]\n', "groups.bunks",
     "members[0].at"),
    ('[groups.heap]\nmembers = [ { kind = "skull", at = "round" } ]\n', "groups.heap", "members[0].at"),
    ('[every]\nmode = "add"\nprops = [ { group = "no_group", at = "centre" } ]\n', "every", "props[0].group"),
    ('once = ["throne", "thrones"]\n', "once", "thrones"),
])
def test_a_bad_layer_entry_is_named_by_its_file_entry_and_field(tmp_path, body, where, fld):
    d = _folder(tmp_path)
    _layer(d, "bad", body)
    errs = _errors(d, ["bad"])
    assert ("bad.toml", where, fld) in _where(errs), [str(e) for e in errs]


def test_a_bad_layer_header_or_file_is_named(tmp_path):
    d = _folder(tmp_path)
    _layer(d, "hdr", '[layer]\nname = "other"\n', head=False)
    assert {("hdr.toml", "layer", "name"), ("hdr.toml", "layer", "description")} <= set(_where(_errors(d, ["hdr"])))
    _layer(d, "none", '[types.ossuary]\nmode = "add"\nprops = []\n', head=False)
    assert ("none.toml", "top level", "layer") in _where(_errors(d, ["none"]))
    _layer(d, "toml", "[types.ossuary\n")
    errs = _errors(d, ["toml"])
    assert errs[0].file == "toml.toml" and errs[0].field == "toml"


def test_every_layers_failures_are_reported_at_once(tmp_path):
    d = _folder(tmp_path)
    _layer(d, "a", '[types.boneyard]\nprops = []\n')
    _layer(d, "b", '[weights.kinds.deep]\nlamps = 1\n')
    assert {("a.toml", "types", "boneyard"), ("b.toml", "weights.kinds.deep", "lamps")} <= set(
        _where(_errors(d, ["a", "b"])))


def test_the_merged_set_is_checked_as_a_whole(tmp_path):
    """A layer can be sound alone and still leave the merged set broken: here, a default
    without every Category. The merged set's failures name the base and its layers."""
    d = _folder(tmp_path)
    _layer(d, "m", '[weights.default]\nmode = "replace"\nlight = 1\n')
    errs = _errors(d, ["m"])
    assert errs and all(e.file == f"{ROOMS_FILE} + m.toml" for e in errs)
    assert ("weights.default", "bare") in [(e.where, e.field) for e in errs]


def test_an_unknown_layer_is_refused_naming_the_known(tmp_path):
    d = _folder(tmp_path)
    _layer(d, "real")
    errs = _errors(d, ["real", "nope"])
    assert _where(errs) == [("nope.toml", "layer", "name")] and "real" in errs[0].expected


# --- listing and the theme map -------------------------------------------------------------------------


def test_layer_names_lists_the_folder(tmp_path):
    d = _folder(tmp_path)
    assert layer_names(d) == {}
    _layer(d, "b", desc="the second")
    _layer(d, "a", desc="the first")
    (d / LAYERS_DIR / "README.md").write_text("not a layer", encoding="utf-8")
    assert list(layer_names(d).items()) == [("a", "the first"), ("b", "the second")]


def test_the_shipped_theme_map_gives_the_tomb_its_layer():
    m = load_decor_themes()
    assert m.themes == {"tomb": ("tomb",)} and m.races == {}
    assert layers_for("tomb", "goblin") == ("tomb",) and layers_for("temple", "goblin") == ()
    assert layers_for("tomb", extra=["x", "tomb", "x"]) == ("tomb", "x")


def test_layers_for_takes_theme_then_race_then_request(tmp_path):
    d = _folder(tmp_path)
    for n in ("tomb", "goblin", "dark", "mine"):
        _layer(d, n)
    (d / THEMES_FILE).write_text('tomb = { layers = ["tomb", "dark"] }\n[races]\ngoblin = { layers = ["goblin", '
                                 '"dark"] }\n', encoding="utf-8")
    assert layers_for("tomb", "goblin", ["mine", "tomb"], path=d) == ("tomb", "dark", "goblin", "mine")
    assert layers_for("temple", "orc", path=d) == ()
    assert layers_for("", "goblin", path=d) == ("goblin", "dark")
    assert load_decor(d, layers=layers_for("tomb", "goblin", path=d)).layers == ("tomb", "dark", "goblin")


def test_a_bad_theme_map_is_named(tmp_path):
    d = _folder(tmp_path)
    _layer(d, "tomb")
    (d / THEMES_FILE).write_text('crypt = { layers = ["tomb"] }\ntomb = { layers = ["tomb", "gone"] }\n'
                                 '[races]\nhobbit = { layers = ["tomb"] }\n', encoding="utf-8")
    with pytest.raises(RuleSetError) as exc:
        load_decor_themes(d)
    assert set(_where(exc.value.errors)) == {(THEMES_FILE, "top level", "crypt"), (THEMES_FILE, "tomb", "layers[1]"),
                                             (THEMES_FILE, "races", "hobbit")}


def test_the_layers_readme_example_loads(tmp_path):
    """rules/decor/layers/README.md's example is a working layer."""
    d = _folder(tmp_path)
    text = (DECOR_DIR / LAYERS_DIR / "README.md").read_text(encoding="utf-8")
    body = re.search(r"```toml\n(.*?)```", text, re.S).group(1)
    name = re.search(r'name\s*=\s*"(\w+)"', body).group(1)
    (d / LAYERS_DIR / f"{name}.toml").write_text(body, encoding="utf-8")
    r = load_decor(d, layers=[name])
    assert r.layers == (name,) and r.types["barracks"].lines[-1].group == "bone_heap"


# --- the worked example: the tomb layer (task 3, Req 3.1) ------------------------------------------


def _unfiled(x):
    """``x`` with the file each line and Group member was written in blanked: a line moved from
    rooms.toml to a layer is the same line."""
    if isinstance(x, (Line, Member)):
        return dataclasses.replace(x, where=("",) + tuple(x.where[1:]))
    if isinstance(x, Recipe):
        return dataclasses.replace(x, lines=_unfiled(x.lines))
    if isinstance(x, Group):
        return dataclasses.replace(x, members=_unfiled(x.members))
    if isinstance(x, tuple):
        return tuple(_unfiled(v) for v in x)
    if isinstance(x, Mapping):
        return {k: _unfiled(v) for k, v in x.items()}
    return x


def _inlined(tmp_path, names, theme=""):
    """A decor folder whose rooms.toml is the shipped base with each layer's tables pasted back
    in, its ``[layer]`` header dropped: the rules before the layers moved out of rooms.toml. A
    layer's own ``[weights.layer]`` goes back as the ``theme``'s entry, where it stood."""
    d = _folder(tmp_path)
    text = (DECOR_DIR / ROOMS_FILE).read_text(encoding="utf-8")
    for n in names:
        body = (DECOR_DIR / LAYERS_DIR / f"{n}.toml").read_text(encoding="utf-8")
        assert not re.search(r"^mode\s*=", body, re.M), f"{n}.toml changes a base entry: it can't be pasted back"
        body = re.sub(r"^\[layer\]\n(?:(?!\[).*\n)*", "", body, flags=re.M)
        text += "\n" + body.replace("[weights.layer]", f"[weights.themes.{theme}]")
    (d / ROOMS_FILE).write_text(text, encoding="utf-8")
    tomllib.loads(text)
    return d


def _tomb_rooms():
    """(room type, kind) for every room a tomb grows: its kinds' types and its arc's."""
    from generators.semantics import ARCHETYPES, kind_types
    arch = ARCHETYPES["tomb"]
    pairs = {(t, k) for k, types in kind_types("tomb").items() for t in types}
    return sorted(pairs | {(t, "") for t in (arch.entrance_type, arch.climax_type, arch.hub_type, *arch.arc)})


def test_base_and_tomb_are_the_rules_before_the_move(tmp_path):
    """The tomb build loads base + tomb (the theme map), and that set is the one rooms.toml held
    with the tomb's tables in it: every field alike (but ``layers``), so a tomb room gets the same
    recipes and Weights, and a tomb build the same bytes (the TOMB golden in test_decor_builds)."""
    names = layers_for("tomb")
    assert names == ("tomb",)
    got = load_decor(layers=names)
    before = load_decor(_inlined(tmp_path, names, theme="tomb"))
    assert got.layers == names and before.layers == ()
    for f in dataclasses.fields(got):
        if f.name not in ("layers", "weights"):
            assert _unfiled(getattr(got, f.name)) == _unfiled(getattr(before, f.name)), f.name
    # The Weights alike but for where the tomb's look stands: the layer's own entry, once the theme's.
    themes = dict(before.weights["themes"])
    assert got.weights["layers"] == {"tomb": themes.pop("tomb")}
    assert {**got.weights, "layers": {}} == {**before.weights, "themes": themes}
    base = load_decor()
    for room_type, kind in _tomb_rooms():
        room = dict(zone_type="dungeon", theme="tomb", kind=kind, room_type=room_type)
        assert got.weights_for(**room) == before.weights_for(**room)
        assert _unfiled(got.recipe_for(room_type, kind)) == _unfiled(before.recipe_for(room_type, kind))
        assert got.weights_for(**room) != base.weights_for(**room)      # the tomb's look did move


def test_the_tomb_layer_holds_only_what_tomb_rooms_alone_reach():
    """A recipe a tomb room reaches that another theme's rooms reach too stays in rooms.toml
    (the theme map gives the layer to tombs only): checked with ``coverage`` across every theme."""
    from ai.schema import VALID_DUNGEON_THEMES
    from generators.decor.rules import coverage
    from generators.semantics import ARCHETYPES, kind_types
    rules = load_decor(layers=["tomb"])
    reach = {}
    for theme in VALID_DUNGEON_THEMES:
        arch = ARCHETYPES[theme]
        for kind, types in kind_types(theme).items():
            for t in types:
                reach.setdefault(rules.which_recipe(t, kind), set()).add(theme)
        arc = (arch.entrance_type, arch.climax_type, arch.hub_type, *arch.arc)
        for recipe in coverage(rules, arc).values():
            reach.setdefault(recipe, set()).add(theme)
    with open(DECOR_DIR / LAYERS_DIR / "tomb.toml", "rb") as f:
        data = tomllib.load(f)
    moved = [f"{s}.{n}" for s in ("kinds", "types", "zones") for n in data.get(s, {})]
    assert all(reach.get(m) == {"tomb"} for m in moved), {m: reach.get(m) for m in moved}
    assert set(data.get("weights", {})) == {"layer"}         # the tomb's look: its own Weights
    assert "tomb" not in load_decor().weights["themes"]