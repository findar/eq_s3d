"""Room walls task 4 (Requirement 5; design W10): style files are checked data.

Each bad value fails with a line naming the file, the table, the field and what was
expected, as the topology rules do, because a prompt will one day write these.
"""

import random
import subprocess
import sys
from pathlib import Path

import pytest

from generators.wall_styles import RECT, WALLS_DIR, load_style, load_styles
from generators.topology.ruleset import RuleSetError

GOOD = """
[style]
name = "s"
description = "d"
finish = [0, 10]
complex = "voronoi"
cell_size_h = 4.0
wobble_h = 1.0
fill = [0.7, 0.8]
floor_relief_h = [0.0, 0.5]
ceiling_spread = [0.1, 0.4]
corridor_break = 0.1

[shapes]
default = { blob = 1 }

[look]
wall = "rock"
floor = "theme"
ceiling = "rock"
"""


def _load(tmp_path, text):
    p = tmp_path / "s.toml"
    p.write_text(text, encoding="utf-8")
    return load_style(p)


def test_a_good_style_loads(tmp_path):
    s = _load(tmp_path, GOOD)
    assert (s.complex, s.fill, s.look["floor"]) == ("voronoi", (0.7, 0.8), "theme")


@pytest.mark.parametrize("old, new, field, expected", [
    ('complex = "voronoi"', 'complex = "marching"', "complex", "voronoi, grid, facet"),
    ('name = "s"', 'name = "other"', "name", "the file's name"),
    ("cell_size_h = 4.0", 'cell_size_h = "big"', "cell_size_h", "a number from"),
    ("cell_size_h = 4.0", "cell_size_h = 0.1", "cell_size_h", "a number from"),
    ("fill = [0.7, 0.8]", "fill = [0.8, 0.7]", "fill", "low <= high"),
    ("fill = [0.7, 0.8]", "fill = [0.2, 0.8]", "fill", "from 0.65"),
    ("fill = [0.7, 0.8]", "fill = 0.7", "fill", "[low, high]"),
    ("ceiling_spread = [0.1, 0.4]", "ceiling_spread = [0.1, 0.9]", "ceiling_spread", "from 0.0 to 0.75"),
    ("corridor_break = 0.1", "corridor_break = 0.9", "corridor_break", "from 0.0 to 0.3"),
    ("corridor_break = 0.1\n", "corridor_break = 0.1\nextra = 1\n", "extra", "one of"),
    ("default = { blob = 1 }", "default = { star = 1 }", "default.star", "rect, blob"),
    ("default = { blob = 1 }", "default = { blob = 0 }", "default.blob", "a weight above 0"),
    ("default = { blob = 1 }", "default = {}", "default", "at least one shape"),
    ("default = { blob = 1 }", "lair = { blob = 1 }", "default", "required"),
    ("default = { blob = 1 }", "default = { blob = 1 }\ndragon = { blob = 1 }", "dragon", "one of"),
    ('wall = "rock"', 'wall = "lava"', "wall", "theme, rock"),
    ('wall = "rock"\n', "", "wall", "required"),
])
def test_a_bad_value_is_named(tmp_path, old, new, field, expected):
    assert old in GOOD
    with pytest.raises(RuleSetError) as err:
        _load(tmp_path, GOOD.replace(old, new))
    lines = [str(e) for e in err.value.errors]
    hit = [line for line in lines if field in line and expected in line]
    assert hit, lines
    assert all(line.startswith("s.toml › ") for line in lines)


def test_a_facet_style_has_no_cell_size_or_fill(tmp_path):
    with pytest.raises(RuleSetError) as err:
        _load(tmp_path, GOOD.replace('"voronoi"', '"facet"'))
    assert {e.field for e in err.value.errors} == {"cell_size_h", "fill"}


def test_every_failure_is_reported_at_once(tmp_path):
    bad = GOOD.replace('"voronoi"', '"marching"').replace('wall = "rock"', 'wall = "lava"')
    with pytest.raises(RuleSetError) as err:
        _load(tmp_path, bad)
    assert {e.field for e in err.value.errors} >= {"complex", "wall"}


def test_the_shipped_styles_load_and_draw():
    styles = load_styles()
    assert set(styles) == {"built", "hewn", "rough"}
    box = (-60.0, -45.0, 60.0, 45.0)
    for s in styles.values():
        for kind in ("entrance", "hall", "hub", "lair", "deep", "chamber"):
            shape = s.pick_shape(kind, random.Random(1))
            outline = s.draw(box, [("E", -9.0, 9.0)], [], shape, 6.0, random.Random(2))
            assert (outline is None) == (shape == RECT)
            if outline is not None:
                assert outline.fill(box) > 0.45


def test_built_is_mostly_plain_rectangles():
    """Finding 1: most stock built rooms are; rock styles have none."""
    styles = load_styles()
    rng = random.Random(3)
    picks = [styles["built"].pick_shape("chamber", rng) for _ in range(400)]
    assert picks.count(RECT) == max(picks.count(s) for s in set(picks)), "the commonest shape"
    assert all(RECT not in table for s in ("rough", "hewn") for table in styles[s].shapes.values())


def _tool(*args):
    root = Path(__file__).resolve().parent.parent
    return subprocess.run([sys.executable, str(root / "scripts/topology_rules.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=root)


def test_check_covers_the_style_files():
    r = _tool("check")
    assert r.returncode == 0, r.stdout
    for name in ("built", "hewn", "rough"):
        assert f"ok    {name}.toml: wall style" in r.stdout


def test_check_reports_a_bad_style(tmp_path):
    p = tmp_path / "s.toml"
    p.write_text(GOOD.replace('"voronoi"', '"marching"'), encoding="utf-8")
    r = _tool("check", str(p))
    assert r.returncode == 1 and "FAIL  s.toml" in r.stdout and "complex" in r.stdout


def test_draw_walls_writes_a_page(tmp_path):
    r = _tool("draw-walls", "--out", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    page = (tmp_path / "walls.html").read_text(encoding="utf-8")
    for name in ("built", "hewn", "rough"):
        assert f"<h2>{name}</h2>" in page
    assert page.count("<svg") >= 12


def test_style_folder_is_where_the_loader_looks():
    assert WALLS_DIR.name == "walls" and (WALLS_DIR / "rough.toml").is_file()
