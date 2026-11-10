"""The stock model catalogue's Tags and their review (roadmap step 11, task 3; P3, Req 3).

The auto-tagger proposes every Tag with a confidence; ``rules/decor/tags.toml`` holds reviewed
Tags, which win, survive rebuilding and re-tagging the catalogue, and are checked strictly
(every bad value named by file, entry and field). Tests that read the install skip without
``EQ_PATH``.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from core.env import env_value
from generators.decor import catalogue as dc
from generators.topology.ruleset import RuleSetError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import prop_catalogue as pc  # noqa: E402

SAMPLE = ("TORCHPOINT", "HLAMP", "PAWHOOK", "CHAIR", "BHROCK1", "BARREL4")


@pytest.fixture(scope="module")
def committed():
    return pc.load()


@pytest.fixture
def small(committed, tmp_path):
    """A catalogue of a few real entries, written as ``build`` writes it."""
    cat = {k: committed[k] for k in ("format", "counts", "failures", "unresolved", "no_objects")}
    cat["models"] = {k: copy.deepcopy(committed["models"][k]) for k in SAMPLE}
    path = tmp_path / "catalogue.json"
    pc.write(cat, path)
    return path


def _tags(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "tags.toml"
    p.write_text(body, encoding="utf-8")
    return p


REVIEW = """
[models]
"TORCHPOINT" = { use = "yes", suits = ["dungeon", "passage"] }
"CHAIR" = { kind = "stool", set = "human", note = "checked" }
"BHROCK1" = { use = "no" }
"""


def _assert_reviewed(cat: dc.Catalogue) -> None:
    t = cat.models["TORCHPOINT"].tags
    assert t.use == "yes" and t.suits == ("dungeon", "passage")
    assert set(t.reviewed) == {"use", "suits"} and t.confidence["use"] == 1.0
    c = cat.models["CHAIR"].tags
    assert (c.kind, c.category, c.set, c.note) == ("stool", "furniture", "human", "checked")
    assert "category" in c.reviewed      # a reviewed kind brings its Category
    assert cat.models["BHROCK1"].tags.use == "no"
    assert set(cat.usable()) == {"TORCHPOINT"}
    assert set(cat.find(kind="torch", mount="wall")) == {"TORCHPOINT"}


# --- P3: reviewed Tags win and survive a rebuild -----------------------------------------------


def test_reviewed_tags_win(small, tmp_path):
    cat = dc.load(small, _tags(tmp_path, REVIEW))
    _assert_reviewed(cat)
    # what the review leaves out keeps the proposal
    raw = json.loads(small.read_text(encoding="utf-8"))["models"]
    assert cat.models["HLAMP"].tags.kind == raw["HLAMP"]["tags"]["kind"]
    assert cat.models["CHAIR"].tags.mount == raw["CHAIR"]["tags"]["mount"]


def test_rebuild_and_retag_keep_reviews(small, tmp_path):
    tags = _tags(tmp_path, REVIEW)
    before = tags.read_bytes()
    raw = pc.load(small)
    for m in raw["models"].values():     # a rebuild from scratch: no tags carried
        m.pop("tags", None)
    pc.write(raw, small)
    pc.tag(pc.load(small), small)
    _assert_reviewed(dc.load(small, tags))
    assert tags.read_bytes() == before   # neither step writes the reviews


def test_build_carries_tags_over():
    assert "tags" in pc.KEPT and "observed" in pc.KEPT


def test_rebuild_from_install_keeps_reviews(tmp_path):
    eq = env_value("EQ_PATH")
    if not eq or not (Path(eq) / "befallen_obj.s3d").is_file():
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    out = tmp_path / "catalogue.json"
    pc.build(Path(eq), out, only=r"^befallen_obj\.s3d$", jobs=1)
    pc.tag(pc.load(out), out)
    tags = _tags(tmp_path, '[models]\n"BHROCK1" = { kind = "brick", use = "yes" }\n')
    for _ in range(2):          # and again after a second rebuild
        cat = dc.load(out, tags)
        assert (cat.models["BHROCK1"].tags.kind, cat.models["BHROCK1"].tags.use) == ("brick", "yes")
        pc.build(Path(eq), out, only=r"^befallen_obj\.s3d$", jobs=1)
        pc.tag(pc.load(out), out)


# --- bad values are named by file, entry and field ----------------------------------------------


@pytest.mark.parametrize("line, where, fld", [
    ('"CHAIR" = { kind = "tabel" }', "models.CHAIR", "kind"),
    ('"CHAIR" = { mount = "roof" }', "models.CHAIR", "mount"),
    ('"CHAIR" = { set = "martian" }', "models.CHAIR", "set"),
    ('"CHAIR" = { era = "modern" }', "models.CHAIR", "era"),
    ('"CHAIR" = { collision = "soft" }', "models.CHAIR", "collision"),
    ('"CHAIR" = { suits = ["kitchen"] }', "models.CHAIR", "suits"),
    ('"CHAIR" = { suits = "barracks" }', "models.CHAIR", "suits"),
    ('"CHAIR" = { use = "maybe" }', "models.CHAIR", "use"),
    ('"CHAIR" = { use = true }', "models.CHAIR", "use"),
    ('"CHAIR" = { colour = "red" }', "models.CHAIR", "colour"),
    ('"CHAIR" = { kind = "table", category = "light" }', "models.CHAIR", "category"),
    ('"NOSUCHMODEL" = { use = "yes" }', "models.NOSUCHMODEL", "entry"),
])
def test_bad_review_named(small, tmp_path, line, where, fld):
    with pytest.raises(RuleSetError) as e:
        dc.load(small, _tags(tmp_path, "[models]\n" + line + "\n"))
    assert any(err.file == "tags.toml" and err.where == where and err.field == fld
               for err in e.value.errors), str(e.value)
    assert f"tags.toml › {where} › {fld}" in str(e.value)


def test_every_bad_value_named_at_once(small, tmp_path):
    body = '[models]\n"CHAIR" = { kind = "tabel", mount = "roof" }\n"HLAMP" = { use = "maybe" }\n'
    with pytest.raises(RuleSetError) as e:
        dc.load(small, _tags(tmp_path, body))
    got = {(err.where, err.field) for err in e.value.errors}
    assert {("models.CHAIR", "kind"), ("models.CHAIR", "mount"), ("models.HLAMP", "use")} <= got


def test_bad_toml_named(small, tmp_path):
    with pytest.raises(RuleSetError) as e:
        dc.load(small, _tags(tmp_path, '[models]\n"CHAIR" = { use = "yes"\n'))
    assert e.value.errors[0].file == "tags.toml" and e.value.errors[0].field == "toml"


def test_declared_kinds_and_sets(small, tmp_path):
    body = ('kinds = { lever_arm = "other" }\nsets = ["centaur"]\n[models]\n'
            '"CHAIR" = { kind = "lever_arm", set = "centaur" }\n')
    t = dc.load(small, _tags(tmp_path, body)).models["CHAIR"].tags
    assert (t.kind, t.category, t.set) == ("lever_arm", "other", "centaur")
    with pytest.raises(RuleSetError) as e:
        dc.load(small, _tags(tmp_path, 'kinds = { Lever = "machinery" }\n[models]\n'))
    assert {err.where for err in e.value.errors} == {"kinds"}


def test_bad_proposed_tag_named(small, tmp_path):
    raw = pc.load(small)
    raw["models"]["HLAMP"]["tags"]["mount"] = "roof"
    del raw["models"]["CHAIR"]["tags"]
    pc.write(raw, small)
    with pytest.raises(RuleSetError) as e:
        dc.load(small, _tags(tmp_path, "[models]\n"))
    got = {(err.file, err.where, err.field) for err in e.value.errors}
    assert ("catalogue.json", "HLAMP", "tags.mount") in got
    assert ("catalogue.json", "CHAIR", "tags") in got


# --- the review line ------------------------------------------------------------------------------


def test_review_line_round_trips(small, tmp_path):
    cat = dc.load(small, _tags(tmp_path, "[models]\n"))
    lines = []
    for key, m in cat.models.items():
        vals = {f: (list(getattr(m.tags, f)) if f == "suits" else getattr(m.tags, f))
                for f in dc.TAG_FIELDS}
        vals["use"] = "yes"
        line = dc.review_line(key, vals)
        assert dc.parse_line(line) == {key: vals}
        lines.append(line)
    again = dc.load(small, _tags(tmp_path, "[models]\n" + "\n".join(lines) + "\n"))
    assert set(again.usable()) == set(SAMPLE)
    assert all(set(m.tags.reviewed) == set(dc.TAG_FIELDS) for m in again.models.values())


# --- the committed catalogue and the auto-tagger ---------------------------------------------------


def test_committed_files_load():
    cat = dc.load()
    assert len(cat.models) == 4651
    for m in cat.models.values():
        t = m.tags
        assert all(0.0 <= t.confidence[f] <= 1.0 for f in dc.TAG_FIELDS)
        # nothing becomes yes without the review (archive decisions 4 and 5)
        assert t.use != "yes" or "use" in t.reviewed, m.key
        # skeletal stays out; a vertex-animated model is in only by review, frozen (decision 24)
        if m.animation == "skeletal" or not m.placed_total:
            assert t.use == "no", m.key


def test_known_names_tagged(committed):
    """Task 2's checks by name: TORCHPOINT 97% wall, HLAMP 99% wall, PAWHOOK 82% ceiling,
    CHAIR 98% floor."""
    want = {"TORCHPOINT": ("light", "torch", "wall"), "HLAMP": ("light", "lamp", "wall"),
            "PAWHOOK": ("hanging", "hook", "ceiling"), "CHAIR": ("furniture", "chair", "floor"),
            "BARREL4": ("container", "barrel", "floor"), "BONEPILE": ("debris", "bone_pile", "floor")}
    for key, (category, kind, mount) in want.items():
        t = committed["models"][key]["tags"]
        assert (t["category"], t["kind"], t["mount"]) == (category, kind, mount), key
        assert t["conf"]["mount"] >= 0.8, key
    assert committed["models"]["PAWHOOK"]["tags"]["set"] == "gnoll"
    assert committed["models"]["GUKCHAIR"]["tags"]["set"] == "froglok"
    assert committed["models"]["PALLET"]["tags"]["set"] != "erudite"   # PA- only before a kind
    assert committed["models"]["HLAMP"]["tags"]["set"] == "neutral"


def test_rejects(committed):
    m = copy.deepcopy(committed["models"]["CHAIR"])
    assert pc.auto_tags("CHAIR", m)["use"] == "review"
    for change, why in ((("animation", "skeletal"), "animated"), (("placed", {"total": 0, "zones": {}}), "never"),):
        e = copy.deepcopy(m)
        e[change[0]] = change[1]
        t = pc.auto_tags("CHAIR", e)
        assert t["use"] == "no" and why in t["why"]["use"]
    e = copy.deepcopy(m)
    e["measured"]["h"] = 400.0
    assert "huge" in pc.auto_tags("CHAIR", e)["why"]["use"]
    e = copy.deepcopy(m)
    e["measured"]["uvs"] = False
    assert pc.auto_tags("CHAIR", e)["use"] == "no"


def test_collision_from_stock_flags(committed):
    for key in ("TORCH1", "CHAIR", "HLAMP"):        # passable in stock (task 6)
        assert committed["models"][key]["tags"]["collision"] == "passable", key
    assert committed["models"]["BARREL4"]["tags"]["collision"] == "solid"


def test_sheet_covers_finding_1(committed):
    keys = pc.sheet_keys(committed)
    assert len(keys) == 583 and len({committed["models"][k]["name"] for k in keys}) == 581


def test_thumbnail_renders(tmp_path, committed):
    eq = env_value("EQ_PATH")
    if not eq or not (Path(eq) / "befallen_obj.s3d").is_file():
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    from PIL import Image
    m = committed["models"]["BHROCK1"]
    rows = pc.render_archive((Path(eq) / m["source"]["archive"], [("BHROCK1", m["name"], m["source"]["wld"])],
                              tmp_path))
    assert rows[0][2] is None, rows
    img = np.asarray(Image.open(tmp_path / rows[0][1]))
    assert img.shape == (pc.THUMB, 2 * pc.THUMB + 6, 4) and (img[..., 3] > 0).mean() > 0.05
