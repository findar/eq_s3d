"""Room layouts tasks 13-16 (Requirements 10-12; design F11-F13): weights in the rules."""

import pytest

from generators.room_scales import (FINISH, FLAT, SCALES, VALUES, Layer, combine, load_scales, peak_weights)
from generators.topology.ruleset import RuleSetError

GOOD = """
[default]
finish = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
structure = { peak = 5, spread = 3 }
clutter = { peak = 3, spread = 3 }
coherence = { finish = 4, structure = 3, clutter = 3 }
"""


def _load(tmp_path, extra="", base=GOOD):
    p = tmp_path / "scales.toml"
    p.write_text(base + extra, encoding="utf-8")
    return load_scales(p)


def _layer(**scales):
    return Layer(scales)


def test_the_shipped_file_loads_and_names_every_scale():
    rules = load_scales()
    assert all(len(rules.default.weights[s]) == VALUES for s in SCALES)
    assert set(rules.coherence) == set(SCALES)


def test_shorthand_peaks_and_falls_to_nothing():
    w = peak_weights(2, 2)
    assert w[2] == 1.0
    assert w[0] == w[4] == pytest.approx(1 / 3)
    assert w[5] == 0.0
    assert peak_weights(0, 0)[1] == 0.0


def test_layers_multiply_value_by_value():
    a, b = (1.0, 2.0) + (0.0,) * 9, (3.0, 4.0) + (1.0,) * 9
    assert combine(FINISH, [_layer(finish=a), _layer(finish=b)])[:3] == (3.0, 8.0, 0.0)


def test_a_layer_without_the_scale_leaves_it_alone():
    a = (1.0, 2.0) + (0.0,) * 9
    assert combine(FINISH, [_layer(finish=a), _layer(clutter=FLAT)]) == a
    assert combine(FINISH, []) == FLAT


def test_override_replaces_everything_less_specific():
    a, b, c = peak_weights(1, 1), peak_weights(9, 1), peak_weights(8, 2)
    got = combine(FINISH, [_layer(finish=a), Layer({FINISH: b}, (FINISH,)), _layer(finish=c)])
    assert got == tuple(x * y for x, y in zip(b, c))


def test_layers_that_disagree_fall_to_the_most_specific():
    low, high = peak_weights(1, 1), peak_weights(9, 1)
    assert combine(FINISH, [_layer(finish=low), _layer(finish=high)]) == high


def test_a_race_with_a_theme_is_a_real_blend():
    """Both layers are felt, whichever way a shared value leans."""
    rules = load_scales()
    ogre = combine(FINISH, rules.layers_for(race="ogre"))
    sanctum = combine(FINISH, rules.layers_for(theme="corrupted_sanctum"))
    blend = combine(FINISH, rules.layers_for(race="ogre", theme="corrupted_sanctum"))
    assert blend not in (ogre, sanctum)
    assert any(blend)


def test_a_temple_is_tidier_than_a_fresh_dig():
    rules = load_scales()
    mean = lambda w: sum(v * x for v, x in enumerate(w)) / sum(w)  # noqa: E731
    temple = mean(combine("clutter", rules.layers_for(theme="temple")))
    dig = mean(combine("clutter", rules.layers_for(overlay="fresh_dig")))
    assert temple < 2 < 6 < dig


def test_a_reclaimed_ogre_cave_keeps_its_walls_and_loses_its_mess():
    rules = load_scales()
    mean = lambda w: sum(v * x for v, x in enumerate(w)) / sum(w)  # noqa: E731
    ogre = rules.layers_for(race="ogre")
    taken = rules.layers_for(race="ogre", overlay="reclaimed")
    assert mean(combine(FINISH, taken)) == pytest.approx(mean(combine(FINISH, ogre)))
    assert mean(combine("clutter", taken)) < mean(combine("clutter", ogre)) - 3


def test_layers_for_is_ordered_and_skips_what_has_no_table():
    rules = load_scales()
    assert rules.layers_for() == (rules.default,)
    assert rules.layers_for(race="ogre", theme="temple", kind="deep", room_type="throne") == (
        rules.default, rules.races["ogre"], rules.themes["temple"], rules.kinds["deep"], rules.types["throne"])
    assert rules.layers_for(room_type="armory") == (rules.default,)


@pytest.mark.parametrize("extra, where, fld", [
    ("[races.ogre]\nfinish = [1, 2]\n", "races.ogre", "finish"),
    ("[races.ogre]\nfinish = [-1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]\n", "races.ogre", "finish"),
    ("[races.ogre]\nfinish = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]\n", "races.ogre", "finish"),
    ("[races.ogre]\nfinish = 3\n", "races.ogre", "finish"),
    ("[races.ogre]\nfinish = { peak = 11, spread = 1 }\n", "races.ogre", "finish.peak"),
    ("[races.ogre]\nfinish = { peak = 5 }\n", "races.ogre", "finish.spread"),
    ("[races.ogre]\nfinish = { peak = 5, spread = 1, override = 1 }\n", "races.ogre", "finish.override"),
    ("[races.ogre]\nfinish = { peak = 5, spread = 1, height = 1 }\n", "races.ogre", "finish.height"),
    ("[races.ogre]\nshine = { peak = 5, spread = 1 }\n", "races.ogre", "shine"),
    ("[races.human]\nfinish = { peak = 5, spread = 1 }\n", "races", "human"),
    ("[themes.nope]\nfinish = { peak = 5, spread = 1 }\n", "themes", "nope"),
    ("[kinds.nope]\nfinish = { peak = 5, spread = 1 }\n", "kinds", "nope"),
    ("[types.nope]\nfinish = { peak = 5, spread = 1 }\n", "types", "nope"),
    ("[nope]\nfinish = 1\n", "top level", "nope"),
])
def test_every_bad_value_is_named(tmp_path, extra, where, fld):
    with pytest.raises(RuleSetError) as exc:
        _load(tmp_path, extra)
    assert any(e.where == where and e.field == fld for e in exc.value.errors), str(exc.value)


@pytest.mark.parametrize("old, new, fld", [
    ('clutter = { peak = 3, spread = 3 }\n', '', "clutter"),
    ('coherence = { finish = 4, structure = 3, clutter = 3 }\n', '', "coherence"),
    ('finish = 4, structure', 'finish = 11, structure', "coherence.finish"),
    ('finish = 4, structure = 3, clutter = 3', 'finish = 4, structure = 3', "coherence.clutter"),
    ('clutter = { peak = 3, spread = 3 }', 'clutter = { peak = 3, spread = 3, override = true }', "override"),
])
def test_the_default_must_be_whole(tmp_path, old, new, fld):
    assert old in GOOD
    with pytest.raises(RuleSetError) as exc:
        _load(tmp_path, base=GOOD.replace(old, new))
    assert any(e.where == "default" and e.field == fld for e in exc.value.errors), str(exc.value)
