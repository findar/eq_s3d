"""Room decor task 7 (Reqs 5, 7; design P7): decor recipes and Sets as checked data.

The usable-model check runs against FIXTURE Tags: until the tag review (task 4) lands,
``rules/decor/tags.toml`` marks almost nothing ``use = "yes"``, so the live check reports
nearly every line unmet, by design.
"""

import importlib.util
import json
import random
import re
import shutil
from pathlib import Path

import pytest

from generators.decor.catalogue import CATEGORIES, DECOR_DIR, KINDS, Catalogue, Model, Tags
from generators.decor.rules import (BARE, CONTROLS, MOUNTS_FILLING, ROOMS_FILE, SETS_FILE, asks, coverage,
                                    draw_count, load_decor, unmet)
from generators.room_layouts import load_layouts
from generators.semantics import ROOM_TYPES
from generators.topology.graph import ROOM_KINDS
from generators.topology.ruleset import RuleSetError

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def rules():
    return load_decor()


def _copy(tmp_path, file="", old="", new=""):
    """The shipped decor rule files in a scratch folder (no catalogue), with one edit."""
    d = tmp_path / "decor"
    if not d.exists():
        d.mkdir(parents=True)
        for f in (ROOMS_FILE, SETS_FILE):
            shutil.copy(DECOR_DIR / f, d / f)
    if file:
        p = d / file
        text = p.read_text(encoding="utf-8")
        if isinstance(old, re.Pattern):
            assert old.search(text), old.pattern
            text = old.sub(new, text, count=1)
        else:
            assert old in text, old
            text = text.replace(old, new, 1)
        p.write_text(text, encoding="utf-8")
    return d


def _errors(folder):
    with pytest.raises(RuleSetError) as exc:
        load_decor(folder)
    return exc.value.errors


def _model(key, kind, mount="floor", set_="neutral", use="yes"):
    tags = Tags(category=KINDS[kind], kind=kind, mount=mount, set=set_, era="classic", collision="solid",
                suits=("dungeon",), use=use)
    return Model(key=key, name=key, archive="x_obj.s3d", wld="x_obj.wld", animation="static", measured={},
                 observed=None, placed={}, textures=(), tags=tags)


def _fixture_catalogue(rules, drop=()):
    """A catalogue with one usable model for the first kind of every line asked for, at its Mount,
    except the kinds in ``drop``."""
    models = {}
    for _, kinds, mount in asks(rules):
        for k in kinds:
            if k in drop:
                continue
            key = f"{k.upper()}_{mount}"
            models[key] = _model(key, k, MOUNTS_FILLING[mount][0])
            break
    return Catalogue(models=models, kinds=dict(KINDS), sets=("neutral",))


# --- the shipped files ----------------------------------------------------------------------------


def test_the_shipped_files_load(rules):
    assert rules.default.lines and rules.every.lines
    assert set(rules.weights["default"].weights) == set(CATEGORIES) | {BARE}
    assert set(rules.controls) == set(CONTROLS)
    for purpose in ("boss", "treasure", "altar", "guard"):        # Req 8.1
        assert rules.dressing_for(purpose), purpose
    assert rules.moves == {"debris": "clutter", "furniture": "structure"}


def test_every_room_type_in_layouts_has_a_recipe_or_falls_back(rules):
    layouts = load_layouts()
    got = coverage(rules, sorted(layouts.types))
    assert set(got) == set(layouts.types)
    for room_type, name in got.items():
        assert name == f"types.{room_type}" or name in {f"kinds.{k}" for k in rules.kinds} | {"default"}
    # A type without its own recipe falls back to its kind's, then the default (Req 7.2).
    lean = load_decor()
    object.__setattr__(lean, "types", {})
    assert lean.which_recipe("barracks", "hall") == "kinds.hall"
    assert lean.which_recipe("barracks", "entrance") == "kinds.entrance"
    assert lean.which_recipe("barracks", "") == "default"
    for kind in ROOM_KINDS:
        own, every = rules.recipe_for("", kind)
        assert every is rules.every and own.name in (f"kinds.{kind}", "default")


def test_a_site_takes_its_kind_recipe_and_no_every_lines(tmp_path, rules):
    assert rules.recipe_for("camp", source="site") == ()
    d = _copy(tmp_path, ROOMS_FILE, "[dressing.boss]",
              '[sites.camp]\nprops = [ { kind = ["crate", "barrel"], at = "scatter", count = [1, 3] } ]\n\n'
              '[dressing.boss]')
    got = load_decor(d).recipe_for("camp", source="site")
    assert [r.name for r in got] == ["sites.camp"]
    errs = _errors(_copy(tmp_path, ROOMS_FILE, "[sites.camp]", "[sites.castle]"))
    assert [(e.file, e.where, e.field) for e in errs] == [(ROOMS_FILE, "sites", "castle")]


# --- P7: every bad value named by file, entry and field --------------------------------------------


@pytest.mark.parametrize("file, old, new, where, fld", [
    (ROOMS_FILE, '{ kind = ["torch", "lantern", "lamp"], at = "on_wall"', '{ kind = ["torch", "lanturn"], at = "on_wall"',
     "every", "props[0].kind"),
    (ROOMS_FILE, '{ kind = ["torch", "lantern", "lamp"], at = "on_wall"', '{ kind = ["torch"], at = "on_roof"',
     "every", "props[0].at"),
    (ROOMS_FILE, re.compile(r'(\[default\]\nprops = \[ \{ kind = \["barrel", "crate", "box"\], at = "along_wall", '
                            r'count = )\[1, 2\]'), r"\g<1>[5, 2]", "default", "props[0].count"),
    (ROOMS_FILE, re.compile(r'(\{ group = "table_set", at = "centre", chance = )0\.25'), r"\g<1>1.5", "default",
     "props[1].chance"),
    (ROOMS_FILE, '{ group = "table_set", at = "centre", chance = 0.25 }',
     '{ group = "table_set", at = "centre", chance = 0.25, by = "mess" }', "default", "props[1].by"),
    (ROOMS_FILE, '{ group = "table_set", at = "centre", chance = 0.25 }', '{ group = "tea_set", at = "centre" }',
     "default", "props[1].group"),
    (ROOMS_FILE, '{ group = "table_set", at = "centre", chance = 0.25 }', '{ group = "table_set", at = "on_wall" }',
     "default", "props[1].at"),
    (ROOMS_FILE, '{ group = "table_set", at = "centre", chance = 0.25 }',
     '{ group = "table_set", kind = "table", at = "centre" }', "default", "props[1].kind"),
    (ROOMS_FILE, "from = 5 }", "from = 11 }", "every", "props[3].from"),
    (ROOMS_FILE, '[types.armory]', '[types.armoury]', "types", "armoury"),
    (ROOMS_FILE, '[kinds.hall]', '[kinds.gallery]', "kinds", "gallery"),
    (ROOMS_FILE, '[dressing.guard]', '[dressing.lurk]', "dressing", "lurk"),
    (ROOMS_FILE, '[dressing.altar]\nprops', '[dressing.ambush]\nprops', "dressing", "altar"),
    (ROOMS_FILE, '{ kind = "bed", at = "row", count = [1, 3] }', '{ kind = "bed", at = "pile", count = [1, 3] }',
     "groups.bunks", "members[1].at"),
    (ROOMS_FILE, '{ kind = "bed", at = "anchor" }', '{ kind = "bed", at = "row" }', "groups.bunks", "members[0].at"),
    (ROOMS_FILE, "[weights.races.goblin]          # Runnyeye: barrels, chairs, torches everywhere\nlight = 1.6",
     "[weights.races.goblin]\nlight = -1", "weights.races.goblin", "light"),
    (ROOMS_FILE, "[weights.races.goblin]          # Runnyeye: barrels, chairs, torches everywhere\nlight = 1.6",
     "[weights.races.goblin]\nlamps = 1.6", "weights.races.goblin", "lamps"),
    (ROOMS_FILE, "[weights.races.kobold]", "[weights.races.hobbit]", "weights.races", "hobbit"),
    (ROOMS_FILE, "bare = 0.26", "bare = 1.5", "weights.default", "bare"),
    (ROOMS_FILE, "light = 1\ncontainer = 1\n", "container = 1\n", "weights.default", "light"),
    (ROOMS_FILE, "[weights.controls.normal]", "[weights.controls.lavish]", "weights.controls", "lavish"),
    (ROOMS_FILE, "debris = { value = 0.15, override = true }", "debris = { value = 0.15, override = 1 }",
     "weights.zone_types.city", "debris.override"),
    (ROOMS_FILE, 'moves = { debris = "clutter"', 'moves = { debris = "mess"', "moves", "debris"),
    (SETS_FILE, 'goblin = ["goblin"]', 'goblin = ["goblins"]', "races", "goblin"),
    (SETS_FILE, 'kobold = ["kobold"]', 'hobbit = ["halfling"]', "races", "hobbit"),
    (SETS_FILE, 'tomb = ["undead"]', 'crypt = ["undead"]', "themes", "crypt"),
    (SETS_FILE, 'city = ["human"]', 'city = "human"', "zone_types", "city"),
    (SETS_FILE, 'iksar = ["froglok"]', 'iksar = ["iksar"]', "allows", "iksar"),
])
def test_a_bad_value_is_named_by_file_entry_and_field(tmp_path, file, old, new, where, fld):
    errs = _errors(_copy(tmp_path, file, old, new))
    assert (file, where, fld) in [(e.file, e.where, e.field) for e in errs], [str(e) for e in errs]


def test_every_failure_of_both_files_is_reported_at_once(tmp_path):
    d = _copy(tmp_path, ROOMS_FILE, "bare = 0.26", "bare = 2")
    _copy(tmp_path, SETS_FILE, 'goblin = ["goblin"]', 'goblin = ["goblins"]')
    _copy(tmp_path, ROOMS_FILE, '[types.armory]', '[types.armoury]')
    got = {(e.file, e.where, e.field) for e in _errors(d)}
    assert {(ROOMS_FILE, "weights.default", "bare"), (ROOMS_FILE, "types", "armoury"),
            (SETS_FILE, "races", "goblin")} <= got


def test_a_bad_toml_file_is_named(tmp_path):
    d = _copy(tmp_path, SETS_FILE, "[races]", "[races")
    errs = _errors(d)
    assert errs[0].file == SETS_FILE and errs[0].field == "toml"


def test_kinds_and_sets_a_review_declares_are_accepted(tmp_path):
    d = _copy(tmp_path, ROOMS_FILE, '{ kind = "bed", at = "anchor" }', '{ kind = "bunk", at = "anchor" }')
    _copy(tmp_path, SETS_FILE, "orc = []", 'orc = ["crushbone"]')
    assert {e.field for e in _errors(d)} >= {"members[0].kind", "orc"}
    (d / "tags.toml").write_text('kinds = { bunk = "furniture" }\nsets = ["crushbone"]\n[models]\n', encoding="utf-8")
    r = load_decor(d)
    assert r.groups["bunks"].members[0].kinds == ("bunk",) and r.sets.sets_for(race="orc")[0] == "crushbone"


# --- Req 7.3: every Tag asked for has a usable model, or the line is named ---------------------------


def test_with_fixture_tags_every_line_is_met(rules):
    assert unmet(rules, _fixture_catalogue(rules)) == []


def test_an_unmet_line_is_named_by_file_entry_and_field(rules):
    got = unmet(rules, _fixture_catalogue(rules, drop=("forge",)))
    assert [(e.file, e.where, e.field) for e in got] == [(ROOMS_FILE, "groups.forge_set", "members[0].kind")]
    # Alternatives: a line is met by any of its kinds, best first or not.
    got = unmet(rules, _fixture_catalogue(rules, drop=("chest",)))
    names = {(e.where, e.field) for e in got}
    assert ("dressing.treasure", "props[0].kind") in names        # chest alone
    assert ("types.vault", "props[0].kind") not in names          # ["chest", "urn"]: the urn meets it


def test_a_model_meets_a_line_only_at_its_mount_and_with_use_yes(rules):
    cat = _fixture_catalogue(rules)
    models = dict(cat.models)
    models["TORCH_wall"] = _model("TORCH_wall", "torch", "floor")       # a floor torch, not a wall one
    for k in [k for k in models if k.startswith(("LANTERN", "LAMP"))]:
        del models[k]
    got = {(e.where, e.field) for e in unmet(rules, Catalogue(models, cat.kinds, cat.sets))}
    assert ("every", "props[0].kind") in got
    models["TORCH_wall"] = _model("TORCH_wall", "torch", "wall", use="review")
    got = {(e.where, e.field) for e in unmet(rules, Catalogue(models, cat.kinds, cat.sets))}
    assert ("every", "props[0].kind") in got
    models["TORCH_wall"] = _model("TORCH_wall", "torch", "wall")
    got = {(e.where, e.field) for e in unmet(rules, Catalogue(models, cat.kinds, cat.sets))}
    assert ("every", "props[0].kind") not in got


def test_a_reviewed_use_yes_in_tags_toml_meets_a_line(tmp_path, rules):
    """The live catalogue with a review: tags.toml's use = "yes" wins over the proposal."""
    from generators.decor.catalogue import CATALOGUE_FILE, load
    entries = json.loads((DECOR_DIR / CATALOGUE_FILE).read_text(encoding="utf-8"))["models"]
    chest = next(k for k, e in sorted(entries.items())
                 if e["tags"]["kind"] == "chest" and e["tags"]["mount"] == "floor")
    none, tags = tmp_path / "none.toml", tmp_path / "tags.toml"
    none.write_text("[models]\n", encoding="utf-8")
    tags.write_text(f'[models]\n"{chest}" = {{ use = "yes" }}\n', encoding="utf-8")
    before = {(e.where, e.field) for e in unmet(rules, load(DECOR_DIR / CATALOGUE_FILE, none))}
    after = {(e.where, e.field) for e in unmet(rules, load(DECOR_DIR / CATALOGUE_FILE, tags))}
    assert ("dressing.treasure", "props[0].kind") in before - after


# --- Req 7.4: Weights by Layer -------------------------------------------------------------------------


def _with_weights(tmp_path, text):
    d = _copy(tmp_path, ROOMS_FILE, "# --- what the room is for", text + "\n# --- what the room is for")
    return load_decor(d)


def test_layers_blend_as_step_9s_scales_do(tmp_path):
    r = _with_weights(tmp_path, "[weights.types.forge]\nlight = 9\n\n[weights.types.armory]\nlight = { value = 4, "
                                "override = true }\n")
    assert r.weights_for("dungeon")["light"] == pytest.approx(1.0)
    assert r.weights_for("dungeon", room_type="forge")["light"] == pytest.approx(3.0)       # sqrt(1 x 9)
    assert r.weights_for("dungeon", race="goblin", room_type="forge")["light"] == pytest.approx((1.6 * 9) ** (1 / 3))
    assert r.weights_for("dungeon", race="goblin", room_type="armory")["light"] == pytest.approx(4.0)   # override
    # The control is on top of the blend, not one more voice in it.
    assert r.weights_for("dungeon", room_type="forge", control="sparse")["light"] == pytest.approx(3.0 * 0.6)
    assert all(v == 0 for k, v in r.weights_for("dungeon", control="none").items() if k != BARE)
    assert sum(r.expected("dungeon", control="none").values()) == 0


def test_written_zeros_leave_the_most_specific_layer_to_decide(tmp_path):
    r = _with_weights(tmp_path, "[weights.kinds.hub]\ndebris = 0\n\n[weights.types.forge]\ndebris = 2\n")
    assert r.weights_for("dungeon", theme="temple", room_type="forge")["debris"] == pytest.approx((0.2 * 2) ** (1 / 3))
    assert r.weights_for("dungeon", kind="hub")["debris"] == 0
    assert r.weights_for("dungeon", kind="hub", room_type="forge")["debris"] == 2.0     # the type decides
    r = _with_weights(tmp_path / "b", "[weights.types.forge]\ndebris = 0\n")
    assert r.weights_for("dungeon", theme="temple", room_type="forge")["debris"] == 0


def test_clutter_moves_debris_and_structure_furniture(rules):
    def debris(c):
        return rules.expected("dungeon", scales={"clutter": c, "structure": 5})["debris"]
    assert debris(0) == 0 < debris(3) < debris(5) < debris(10)
    assert debris(10) == pytest.approx(2 * debris(5), rel=0.25)
    light = [rules.expected("dungeon", scales={"clutter": c})["light"] for c in (0, 5, 10)]
    assert light[0] == light[1] == light[2]
    furn = [rules.expected("dungeon", scales={"structure": s})["furniture"] for s in (0, 5, 10)]
    assert furn[0] == 0 < furn[1] < furn[2]
    # `from`: the webs and mushrooms line is there only from clutter 5 up.
    line = rules.every.lines[3]
    assert line.at_least == 5 and rules.factor(line, {"debris": 1.0}, {"clutter": 4}) == 0
    assert rules.factor(line, {"debris": 1.0}, {"clutter": 5}) == 1.0


def test_the_figures_sit_in_finding_1s_bands(rules):
    """Design finding 1: dungeon rooms 2.9-6.8 Props (p25-p75 of zone means), cities 4.0-12.5; a
    dungeon's lights and debris about a third each, a city's furniture over a quarter."""
    for clutter in (3, 5):
        e = rules.expected("dungeon", scales={"clutter": clutter, "structure": 5})
        total = sum(e.values())
        assert 2.9 <= total <= 6.8
        assert 0.21 <= e["light"] / total <= 0.45 and 0.20 <= e["debris"] / total <= 0.56
        assert 0.03 <= e["container"] / total <= 0.11 and 0.09 <= e["furniture"] / total <= 0.18
        c = rules.expected("city", scales={"clutter": clutter, "structure": 5})
        ctotal = sum(c.values())
        assert 4.0 <= ctotal <= 12.5 and ctotal > total
        assert 0.23 <= c["furniture"] / ctotal <= 0.36 and c["debris"] / ctotal <= 0.07
    assert rules.weights_for("dungeon")[BARE] == pytest.approx(0.26)
    # The dead keep a dark, littered room (Befallen: 1% light, 68% debris).
    tomb = rules.expected("dungeon", theme="tomb")
    assert tomb["light"] / sum(tomb.values()) < 0.2 and tomb["debris"] / sum(tomb.values()) > 0.5


def test_draw_count_has_the_expected_mean(rules):
    line = rules.every.lines[2]           # rocks and bones, [1, 3]
    rng = random.Random(7)
    for factor in (0.6, 1.0, 1.7):
        n = 20000
        mean = sum(draw_count(line, factor, rng) for _ in range(n)) / n
        assert mean == pytest.approx(2.0 * factor * line.chance, rel=0.03)
    assert draw_count(line, 0.0, rng) == 0


# --- Req 5: Sets ----------------------------------------------------------------------------------------


def test_a_room_takes_its_race_theme_and_zone_sets_then_neutral(rules):
    s = rules.sets
    assert s.sets_for("dungeon", "goblin", "tomb") == ("goblin", "undead", "neutral")
    assert s.sets_for("city") == ("human", "neutral")
    assert s.sets_for("dungeon", "orc") == ("neutral",)
    assert s.sets_for("dungeon", "sarnak", "ice_keep") == ("iksar", "coldain", "neutral")


def test_two_cultures_share_a_room_only_when_allowed(rules):
    s = rules.sets
    assert s.may_share("goblin", "neutral") and s.may_share("goblin", "goblin")
    assert not s.may_share("goblin", "gnoll")
    assert s.may_share("iksar", "froglok") and s.may_share("froglok", "iksar")     # either way round
    assert s.may_share("goblin", "undead") and not s.may_share("goblin", "dark_elf")


# --- scripts/topology_rules.py ---------------------------------------------------------------------


def _script():
    spec = importlib.util.spec_from_file_location("topology_rules", ROOT / "scripts" / "topology_rules.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tiny_catalogue(folder: Path, kinds_mounts):
    """A catalogue.json of one proposed-``use = "yes"`` model per (kind, Mount)."""
    conf = {f: 0.9 for f in ("category", "kind", "mount", "set", "era", "collision", "suits", "use")}
    models = {}
    for kind, mount in kinds_mounts:
        key = f"{kind.upper()}_{mount.upper()}"
        models[key] = {"name": key, "source": {"archive": "x_obj.s3d", "wld": "x_obj.wld"},
                       "tags": {"category": KINDS[kind], "kind": kind, "mount": mount, "set": "neutral",
                                "era": "classic", "collision": "solid", "suits": ["dungeon"], "use": "yes",
                                "conf": conf, "why": {}}}
    (folder / "catalogue.json").write_text(json.dumps({"models": models}), encoding="utf-8")
    (folder / "tags.toml").write_text("[models]\n", encoding="utf-8")


def test_check_names_unmet_lines_and_fails_on_them_only_when_strict(tmp_path, capsys):
    tr = _script()
    d = _copy(tmp_path)
    r = load_decor(d)
    _tiny_catalogue(d, [(kinds[0], MOUNTS_FILLING[mount][0]) for _, kinds, mount in asks(r) if kinds[0] != "forge"])
    assert tr.main(["check", str(d)]) == 0
    out = capsys.readouterr().out
    assert "rooms.toml › groups.forge_set › members[0].kind: found forge (floor)" in out
    assert "1 of" in out and "all checks passed" in out
    assert tr.main(["check", str(d), "--strict"]) == 1
    _tiny_catalogue(d, [(kinds[0], MOUNTS_FILLING[mount][0]) for _, kinds, mount in asks(r)])
    assert tr.main(["check", str(d), "--strict"]) == 0
    assert "every Tag asked for has a usable model" in capsys.readouterr().out


def test_check_fails_on_a_bad_decor_file(tmp_path, capsys):
    d = _copy(tmp_path, ROOMS_FILE, "bare = 0.26", "bare = 2")
    assert _script().main(["check", str(d / ROOMS_FILE)]) == 1
    assert "rooms.toml › weights.default › bare" in capsys.readouterr().out


def test_draw_decor_writes_a_page(tmp_path):
    assert _script().main(["draw-decor", "--out", str(tmp_path)]) == 0
    page = (tmp_path / "decor.html").read_text(encoding="utf-8")
    assert "types.barracks" in page and "<svg" in page and "Dressing" in page
