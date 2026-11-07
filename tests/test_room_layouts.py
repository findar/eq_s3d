"""Room layouts task 5 (Requirement 5; design F6): recipes are checked data, every room type has
one, and each failure names its file, table and field.
"""

import random
import subprocess
import sys
from pathlib import Path

import pytest

from generators.room_features import DAIS, PILLAR, SQUARE
from generators.room_layouts import LAYOUTS_FILE, load_layouts, place
from generators.semantics import ROOM_TYPES
from generators.topology.ruleset import RuleSetError
from generators.zone_spec import RoomSpec

ALL_TYPES = "\n".join(f"[types.{n}]\nfeatures = []" for n in sorted(ROOM_TYPES))
GOOD = '[default]\nfeatures = [ { kind = "pillar", at = "rows" } ]\n' + ALL_TYPES + "\n"


def _load(tmp_path, text):
    p = tmp_path / "layouts.toml"
    p.write_text(text, encoding="utf-8")
    return load_layouts(p)


def test_a_good_file_loads(tmp_path):
    rl = _load(tmp_path, GOOD)
    assert rl.default[0].kind == PILLAR and rl.types["throne"] == ()


@pytest.mark.parametrize("line, field, expected", [
    ('{ kind = "statue", at = "rows" }', "kind", "pillar, plinth, boulder, dais"),
    ('{ kind = "pillar", at = "nowhere" }', ".at", "centre, far_end"),
    ('{ kind = "pillar" }', ".at", "required"),
    ('{ kind = "pillar", at = "rows", count = -1 }', "count", "from 0 to 24"),
    ('{ kind = "pillar", at = "rows", count = [3, 1] }', "count", "from 0 to 24"),
    ('{ kind = "pillar", at = "rows", side_h = 99 }', "side_h", "from 0.5 to 8.0"),
    ('{ kind = "pillar", at = "rows", chance = 2 }', "chance", "from 0.0 to 1.0"),
    ('{ kind = "pillar", at = "rows", poi = "lunch" }', "poi", "boss, treasure"),
    ('{ kind = "pillar", at = "rows", colour = 1 }', "colour", "one of"),
])
def test_a_bad_line_is_named(tmp_path, line, field, expected):
    with pytest.raises(RuleSetError) as err:
        _load(tmp_path, GOOD.replace('{ kind = "pillar", at = "rows" }', line))
    text = [str(e) for e in err.value.errors]
    assert any(field in t and expected in t for t in text), text
    assert all(t.startswith("layouts.toml › ") for t in text)


def test_every_room_type_needs_a_recipe(tmp_path):
    with pytest.raises(RuleSetError) as err:
        _load(tmp_path, GOOD.replace("[types.throne]\nfeatures = []\n", ""))
    assert any("throne" in str(e) and "every room type" in str(e) for e in err.value.errors)


def test_an_unknown_type_or_kind_is_named(tmp_path):
    with pytest.raises(RuleSetError) as err:
        _load(tmp_path, GOOD + "[types.pantry]\nfeatures = []\n[kinds.attic]\nfeatures = []\n")
    fields = {e.field for e in err.value.errors}
    assert {"pantry", "attic"} <= fields


def test_the_shipped_file_covers_every_room_type_and_chooses_in_order():
    rl = load_layouts()
    assert set(rl.types) == set(ROOM_TYPES)
    assert rl.recipe_for("throne", "deep")[0] == "type:throne"
    assert rl.recipe_for("", "deep")[0] == "kind:deep"
    assert rl.recipe_for("", "passage")[0] == "default"
    assert any(a.kind == DAIS and a.poi == "boss" for a in rl.types["throne"])


@pytest.mark.parametrize("name", sorted(ROOM_TYPES))
def test_each_recipe_places_without_failing(name):
    rl = load_layouts()
    room = RoomSpec("r", 0.0, 0.0, width=120.0, depth=90.0, height=40.0)
    placed = place(room, [("E", -9.0, 9.0)], [], rl.types[name], 6.0, SQUARE, random.Random(3))
    assert isinstance(placed.dropped, list)


def _tool(*args):
    root = Path(__file__).resolve().parent.parent
    return subprocess.run([sys.executable, str(root / "scripts/topology_rules.py"), *args], capture_output=True,
                          text=True, encoding="utf-8", cwd=root)


def test_check_covers_the_file():
    r = _tool("check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ok    layouts.toml: room layouts" in r.stdout


def test_draw_rooms_writes_a_page(tmp_path):
    r = _tool("draw-rooms", "--out", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    page = (tmp_path / "rooms.html").read_text(encoding="utf-8")
    assert "<h2>type throne</h2>" in page and page.count("<svg") >= 60


def test_the_file_is_where_the_loader_looks():
    assert LAYOUTS_FILE.is_file() and LAYOUTS_FILE.parent.name == "rooms"


def test_rows_with_no_count_fill_their_length():
    """A throne room's rows came out as one pillar: a recipe gives no count, and it meant 1."""
    rl = load_layouts()
    room = RoomSpec("r", 0.0, 0.0, width=200.0, depth=100.0, height=40.0)
    placed = place(room, [("E", -9.0, 9.0), ("W", -9.0, 9.0)], [], [a for a in rl.types["barracks"]], 6.0, SQUARE,
                   random.Random(1))
    assert len(placed.features) >= 4
