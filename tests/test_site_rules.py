"""Wilderness POIs task 5 (Req 5; design P6): Site recipes, Inhabitants and biomes as checked data."""

import random
import shutil

import pytest
from hypothesis import example, given, settings, strategies as st

from generators.sites.rules import (SITE_KINDS, SITES_DIR, combine_weights, load_sites)
from generators.topology.ruleset import RuleSetError


def _copy(tmp_path, file="", old="", new=""):
    """The shipped Site files in a scratch folder, with one edit to one of them."""
    d = tmp_path / "sites"
    if not d.exists():
        shutil.copytree(SITES_DIR, d)
    if file:
        p = d / file
        text = p.read_text(encoding="utf-8")
        assert old in text, old
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return d


def _errors(folder):
    with pytest.raises(RuleSetError) as exc:
        load_sites(folder)
    return exc.value.errors


def test_the_shipped_files_load_with_a_recipe_for_every_kind():
    rules = load_sites()
    assert set(SITE_KINDS) <= set(rules.kinds)
    assert {"human", "orc", "gnoll", "centaur"} <= set(rules.inhabitants)
    assert "plains" in rules.biomes
    for recipe in rules.kinds.values():
        assert recipe.structures and recipe.pois
        assert {line.kind for line in recipe.structures} <= set(rules.structures)
    camp = rules.kinds["camp"]
    assert any(p.purpose == "Light_Spot" and p.at == "fire_ring" for p in camp.pois)


@pytest.mark.parametrize("file, old, new, where, fld", [
    ("sites.toml", 'arrangement = "ring"', 'arrangement = "spiral"', "kinds.camp", "arrangement"),
    ("sites.toml", '{ kind = "tent", count = [2, 5]', '{ kind = "yurt", count = [2, 5]', "kinds.camp",
     "structures[1].kind"),
    ("sites.toml", 'count = [2, 5]', 'count = [5, 2]', "kinds.camp", "structures[1].count"),
    ("sites.toml", 'count = [2, 5], face = "in"', 'count = [2, 5], face = "up"', "kinds.camp", "structures[1].face"),
    ("sites.toml", 'at = "row", side = "open", chance = 0.5', 'at = "row", side = "open", chance = 2',
     "kinds.hut", "structures[1].chance"),
    ("sites.toml", 'radius = 24, slope_deg = 8', 'radius = 24, slope_deg = 80', "kinds.camp", "ground.slope_deg"),
    ("sites.toml", 'radius = 24, slope_deg = 8, spacing = 400, ', 'radius = 24, slope_deg = 8, ', "kinds.camp",
     "ground.spacing"),
    ("sites.toml", 'likes = { near_water = 4', 'likes = { near_lava = 4', "kinds.camp", "likes.near_lava"),
    ("sites.toml", 'purpose = "Light_Spot"', 'purpose = "Torch"', "kinds.camp", "pois[0].purpose"),
    ("sites.toml", 'purpose = "Light_Spot", at = "fire_ring"', 'purpose = "Light_Spot", at = "barn"',
     "kinds.camp", "pois[0].at"),
    ("sites.toml", 'purpose = "interior", at = "hut" },\n]', 'purpose = "interior", at = "centre" },\n]',
     "kinds.hut", "pois[0].at"),
    ("sites.toml", '[structures.tent]\nradius = 6', '[structures.tent]\nradius = -6', "structures.tent", "radius"),
    ("sites.toml", '[structures.hut]\nradius = 9\nheight = 16\nenterable = true',
     '[structures.hut]\nradius = 9\nheight = 16\nenterable = "yes"', "structures.hut", "enterable"),
    ("sites.toml", '[structures.barn]', '[structures.castle]', "structures", "castle"),
    ("sites.toml", '[kinds.ruin]', '[kinds.ruins]', "kinds", "ruin"),
    ("inhabitants.toml", 'materials = "orc"', 'materials = "Orc Hide"', "inhabitants.orc", "materials"),
    ("inhabitants.toml", 'variants = { tent = "hide", tower', 'variants = { yurt = "hide", tower',
     "inhabitants.orc", "variants.yurt"),
    ("inhabitants.toml", 'swap = { tent = "lean_to" }', 'swap = { hut = "tent" }', "inhabitants.centaur",
     "swap.hut"),
    ("inhabitants.toml", 'weights = { camp = 4, hut = 0', 'weights = { camp = -4, hut = 0', "inhabitants.orc",
     "weights.camp"),
    ("inhabitants.toml", 'weights = { camp = 4, hut = 0', 'weights = { castle = 4, hut = 0', "inhabitants.orc",
     "weights.castle"),
    ("inhabitants.toml", '[inhabitants.orc]\nmaterials', '[inhabitants.orc]\ncolour = 1\nmaterials',
     "inhabitants.orc", "colour"),
    ("biomes.toml", 'density = [0.8, 2.0]', 'density = [2.0, 0.8]', "biomes.plains", "density"),
    ("biomes.toml", 'inhabitants = { human = 4', 'inhabitants = { elf = 4', "biomes.plains", "inhabitants.elf"),
    ("biomes.toml", 'weights = { camp = 4', 'weights = { camp = "lots"', "biomes.plains", "weights.camp"),
    ("biomes.toml", '[biomes.plains]', '[biomes.tundra]', "biomes", "tundra"),
])
def test_every_bad_value_is_named_by_file_entry_and_field(tmp_path, file, old, new, where, fld):
    errors = _errors(_copy(tmp_path, file, old, new))
    assert any(e.file == file and e.where == where and e.field == fld for e in errors), \
        "\n".join(str(e) for e in errors)


def test_every_failure_of_all_three_files_comes_at_once(tmp_path):
    d = _copy(tmp_path, "sites.toml", 'arrangement = "ring"', 'arrangement = "spiral"')
    _copy(tmp_path, "biomes.toml", 'density = [0.8, 2.0]', 'density = 3')
    files = {e.file for e in _errors(d)}
    assert files == {"sites.toml", "biomes.toml"}


@given(st.sampled_from(["structures.tent.radius", "structures.tower.height", "kinds.camp.ground.radius",
                        "kinds.shrine.ground.margin", "kinds.watchtower.likes.high_ground"]),
       st.one_of(st.floats(allow_nan=False, allow_infinity=False).filter(lambda v: v < -1e-9 or v > 5000),
                 st.text(st.characters(min_codepoint=32, max_codepoint=126), max_size=4), st.booleans()))
@example("structures.tent.radius", 0.0)
@example("kinds.camp.ground.radius", 1e6)
@example("kinds.watchtower.likes.high_ground", True)
@settings(deadline=None)     # each example writes a file
def test_any_bad_number_is_named(path, value):
    """A bad number in any numeric field, of any wrong type or size, is named where it is."""
    import tomllib
    parts = path.split(".")
    data = tomllib.loads((SITES_DIR / "sites.toml").read_text(encoding="utf-8"))
    tbl = data
    for p in parts[:-1]:
        tbl = tbl[p]
    tbl[parts[-1]] = value
    rules = _parse(data)
    if path.startswith("structures."):
        where, fld = ".".join(parts[:2]), parts[2]
    else:
        where, fld = ".".join(parts[:2]), ".".join(parts[2:])
    assert any(e.file == "sites.toml" and e.where == where and e.field == fld for e in rules), \
        "\n".join(str(e) for e in rules)


_SCRATCH = {}


def _parse(sites_data):
    """Load with ``sites_data`` as sites.toml beside the shipped other two; the errors."""
    import tempfile
    from pathlib import Path
    if "dir" not in _SCRATCH:
        _SCRATCH["tmp"] = tempfile.TemporaryDirectory()
        _SCRATCH["dir"] = Path(_SCRATCH["tmp"].name) / "s"
        shutil.copytree(SITES_DIR, _SCRATCH["dir"])
    (_SCRATCH["dir"] / "sites.toml").write_text(_toml(sites_data), encoding="utf-8")
    try:
        load_sites(_SCRATCH["dir"])
    except RuleSetError as exc:
        return exc.errors
    return ()


def _toml(data) -> str:
    """Just enough TOML writing for the Site files."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(v, float):
            return repr(v)
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{ " + ", ".join(f"{k} = {val(x)}" for k, x in v.items()) + " }"
        return str(v)
    out = []
    for section, entries in data.items():
        for name, body in entries.items():
            out.append(f"[{section}.{name}]")
            out += [f"{k} = {val(v)}" for k, v in body.items()]
    return "\n".join(out) + "\n"


def test_a_kind_named_in_weights_needs_a_recipe(tmp_path):
    """Weights can name only kinds that have a recipe; the six decided kinds always need one."""
    d = _copy(tmp_path, "sites.toml", "[kinds.shrine]", "[kinds.temple]")
    errors = _errors(d)
    assert any(e.where == "kinds" and e.field == "shrine" for e in errors)
    assert any(e.file == "inhabitants.toml" and e.field == "weights.shrine" for e in errors)


def test_a_swap_that_walls_up_an_interior_is_named(tmp_path):
    d = _copy(tmp_path, "inhabitants.toml", 'swap = { tent = "lean_to" }', 'swap = { tent = "lean_to", hut = "tower" }')
    errors = _errors(d)
    assert any(e.where == "inhabitants.centaur" and e.field == "swap.hut" for e in errors), errors


def test_chance_is_weight_over_sum_of_the_layers_multiplied():
    rules = load_sites()
    for who in rules.inhabitants:
        got = rules.kind_chances("plains", who)
        b, i = rules.biomes["plains"].weights, rules.inhabitants[who].weights
        w = {k: (b.get(k, 1.0) * i.get(k, 1.0)) ** 0.5 for k in rules.kinds}
        assert got == pytest.approx({k: v / sum(w.values()) for k, v in w.items()})
        assert sum(got.values()) == pytest.approx(1.0)
    # A zero anywhere is never; the orc never farms.
    assert rules.kind_chances("plains", "orc")["farmstead"] == 0.0
    mix = rules.inhabitant_chances("plains")
    raw = rules.biomes["plains"].inhabitants
    assert mix == pytest.approx({k: v / sum(raw.values()) for k, v in raw.items()})


def test_a_control_is_a_third_layer_and_zeros_fall_to_the_most_specific():
    rules = load_sites()
    farm = rules.kind_chances("plains", "human", control={k: (1.0 if k == "farmstead" else 0.0) for k in rules.kinds})
    assert farm["farmstead"] == pytest.approx(1.0)
    # Orcs never farm; asked for a farm anyway, the control alone decides, as step 9's Scales do.
    orc = rules.kind_chances("plains", "orc", control={k: (1.0 if k == "farmstead" else 0.0) for k in rules.kinds})
    assert orc["farmstead"] == pytest.approx(1.0)
    assert combine_weights(("a", "b"), [None, {"a": 2.0}]) == {"a": 2.0, "b": 1.0}


def test_draws_follow_the_chances():
    rules = load_sites()
    rng = random.Random(0)
    drawn = [rules.draw_kind("plains", "centaur", rng) for _ in range(4000)]
    want = rules.kind_chances("plains", "centaur")
    for k, p in want.items():
        assert drawn.count(k) / len(drawn) == pytest.approx(p, abs=0.03)
    assert rules.draw_inhabitant("plains", rng, pinned="orc") == "orc"


def test_an_inhabitant_builds_with_its_swaps_and_variants():
    rules = load_sites()
    camp = rules.recipe_for("camp", "centaur")
    assert [line.kind for line in camp.structures] == ["fire_ring", "lean_to"]
    assert camp.structures[1].variant == "hide"
    assert rules.recipe_for("camp", "orc").structures[1].variant == "hide"
    assert rules.recipe_for("camp", "human").structures[1].variant == "canvas"


def test_the_rule_tooling_checks_and_draws_the_site_files(tmp_path, capsys):
    import importlib.util
    root = SITES_DIR.parents[1]
    spec = importlib.util.spec_from_file_location("topology_rules", root / "scripts" / "topology_rules.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert tool.main(["check", str(SITES_DIR)]) == 0
    bad = _copy(tmp_path, "biomes.toml", "density = [0.8, 2.0]", "density = 3")
    assert tool.main(["check", str(bad / "biomes.toml")]) == 1
    assert "biomes.toml › biomes.plains › density" in capsys.readouterr().out
    assert tool.main(["draw-sites", "--out", str(tmp_path / "out")]) == 0
    page = (tmp_path / "out" / "sites.html").read_text(encoding="utf-8")
    assert all(f"<h2>{k}</h2>" in page for k in SITE_KINDS)
