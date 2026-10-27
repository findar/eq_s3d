"""
tests/test_paths.py
-------------------
Unit tests for ``core.paths`` (Req 10.1, 10.2).

Pins the filesystem-confinement contract:

* ``OutputRoot.path`` / ``contains`` reject any path that resolves outside the
  root (a ``..`` traversal and an absolute-elsewhere path both raise), while
  writes and moves inside the root succeed.
* ``OutputRoot.remove_tree`` NEVER recurses through a junction / symlink — it
  unlinks the link itself and leaves the target intact. This is the
  safety-critical invariant (the lessons-learned gotcha that gutted
  ``web/node_modules`` via ``git worktree remove`` / ``Remove-Item -Recurse``
  following a junction). The junction/symlink case is guarded so it skips on a
  platform that cannot create one.
* ``assert_output_allowed`` refuses an output dir that is inside, equal to, or
  contains the EQ install, and is a no-op when EQ_PATH is unset.
* ``new_zone_id`` has the ``<prefix>_<digits>_<6hex>`` shape, is lowercase, and
  is unique across calls.
"""

from __future__ import annotations

import os
import re
import subprocess

import pytest

from core.paths import (
    OutputRoot,
    OutsideOutputError,
    assert_output_allowed,
    new_zone_id,
)


# ---------------------------------------------------------------------------
# contains / path confinement
# ---------------------------------------------------------------------------

def test_path_and_contains_inside_root(tmp_path):
    root = OutputRoot(tmp_path)
    inside = root.path("sub", "file.eqg")
    assert root.contains(inside)
    assert root.contains(tmp_path)  # the root itself counts as contained.
    # path() returns a resolved absolute path under the root.
    assert str(inside).startswith(str(tmp_path.resolve()))


def test_path_rejects_dotdot_escape(tmp_path):
    root = OutputRoot(tmp_path / "out")
    with pytest.raises(OutsideOutputError):
        root.path("..", "escape.txt")


def test_path_rejects_absolute_outside(tmp_path):
    root = OutputRoot(tmp_path / "out")
    outside = tmp_path / "elsewhere" / "x.txt"
    assert not root.contains(outside)
    with pytest.raises(OutsideOutputError):
        root.path(str(outside))


# ---------------------------------------------------------------------------
# checked writes / move stay inside
# ---------------------------------------------------------------------------

def test_write_bytes_text_and_mkdir_inside(tmp_path):
    root = OutputRoot(tmp_path)
    d = root.mkdir("zone", "v1")
    assert d.is_dir() and root.contains(d)

    b = root.write_bytes("zone/v1/a.eqg", b"\x00\x01\x02")
    assert b.read_bytes() == b"\x00\x01\x02"

    t = root.write_text("zone/v1/a.zone.json", "{}")
    assert t.read_text(encoding="utf-8") == "{}"


def test_replace_moves_inside(tmp_path):
    root = OutputRoot(tmp_path)
    src = root.write_bytes(".attempts/z/a0/f.bin", b"payload")
    dst = root.path("z", "v1", "f.bin")
    dst.parent.mkdir(parents=True, exist_ok=True)
    root.replace(src, dst)
    assert not src.exists()
    assert dst.read_bytes() == b"payload"


def test_remove_tree_removes_real_directory(tmp_path):
    root = OutputRoot(tmp_path)
    root.write_bytes("scratch/a/one.bin", b"1")
    root.write_bytes("scratch/a/b/two.bin", b"2")
    scratch = root.path("scratch")
    root.remove_tree(scratch)
    assert not scratch.exists()


def test_remove_tree_missing_is_noop(tmp_path):
    root = OutputRoot(tmp_path)
    # Should not raise on a path that does not exist.
    root.remove_tree(root.path("does", "not", "exist"))


# ---------------------------------------------------------------------------
# remove_tree must NOT follow a junction / symlink into its target
# ---------------------------------------------------------------------------

def _make_dir_link(link: str, target: str) -> bool:
    """Create a directory junction (Windows) or dir symlink; return success."""
    if os.name == "nt":
        # Directory junction: no admin rights needed, unlike a symlink.
        res = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link, target],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0 and os.path.isdir(link)
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


def test_remove_tree_unlinks_junction_without_deleting_target(tmp_path):
    """SAFETY-CRITICAL: removing a dir containing a junction must unlink the
    junction as a link and leave the junction's target (and its files) intact."""
    root_dir = tmp_path / "out"
    target_dir = tmp_path / "target"  # OUTSIDE the output root, like node_modules.
    (root_dir).mkdir()
    target_dir.mkdir()
    (target_dir / "precious.bin").write_bytes(b"do-not-delete")

    link = root_dir / "link_to_target"
    if not _make_dir_link(str(link), str(target_dir)):
        pytest.skip("platform cannot create a directory junction/symlink")

    root = OutputRoot(root_dir)
    # Remove the whole output root: it contains a junction pointing outside.
    root.remove_tree(root.path())

    assert not root_dir.exists(), "the output root (and the link) should be gone"
    assert target_dir.exists(), "the junction target must NOT be followed/deleted"
    assert (target_dir / "precious.bin").read_bytes() == b"do-not-delete"


# ---------------------------------------------------------------------------
# assert_output_allowed
# ---------------------------------------------------------------------------

def test_assert_output_allowed_refuses_output_inside_eq(tmp_path):
    eq = tmp_path / "everquest"
    out = eq / "subdir" / "output"
    with pytest.raises(OutsideOutputError):
        assert_output_allowed(out, eq)


def test_assert_output_allowed_refuses_output_containing_eq(tmp_path):
    out = tmp_path / "root"
    eq = out / "everquest"
    with pytest.raises(OutsideOutputError):
        assert_output_allowed(out, eq)


def test_assert_output_allowed_refuses_equal(tmp_path):
    same = tmp_path / "everquest"
    with pytest.raises(OutsideOutputError):
        assert_output_allowed(same, same)


def test_assert_output_allowed_ok_for_disjoint(tmp_path):
    out = tmp_path / "output"
    eq = tmp_path / "everquest"
    assert_output_allowed(out, eq)  # disjoint siblings: fine.


def test_assert_output_allowed_noop_for_none(tmp_path):
    assert_output_allowed(tmp_path / "output", None)
    assert_output_allowed(tmp_path / "output", "")


# ---------------------------------------------------------------------------
# new_zone_id
# ---------------------------------------------------------------------------

_ZONE_ID_RE = re.compile(r"^[a-z0-9_]+_\d+_[0-9a-f]{6}$")


def test_new_zone_id_shape_default_prefix():
    zid = new_zone_id()
    assert zid.startswith("gen_")
    assert _ZONE_ID_RE.match(zid), zid
    assert zid == zid.lower()


def test_new_zone_id_custom_prefix_lowercased():
    zid = new_zone_id(prefix="MyZone")
    assert zid.startswith("myzone_")
    assert _ZONE_ID_RE.match(zid), zid


def test_new_zone_id_unique_across_calls():
    ids = {new_zone_id() for _ in range(50)}
    assert len(ids) == 50
