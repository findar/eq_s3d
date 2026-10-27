"""
core/paths.py
-------------
Filesystem confinement for the build path (Req 10.1, 10.2).

Every write, move and remove a build performs must land *inside* a single
Output_Directory. ``OutputRoot`` wraps that directory and offers only
confinement-checked operations: a path that resolves outside the root raises
``OutsideOutputError`` and nothing is written. The Pipeline, ``ZoneBuilder`` and
the CLI/server route their writes through an ``OutputRoot`` (wired by task 19.5);
this module is the home of the guard and of ``new_zone_id`` (Req 10.1).

The safety-critical piece is ``OutputRoot.remove_tree``. On Windows the parallel
agent worktrees share ``web/node_modules`` through a *directory junction*, and a
naive recursive delete (``shutil.rmtree`` / ``Remove-Item -Recurse``) follows
that junction INTO its target and deletes the real files on the other side — the
lessons-learned gotcha that gutted the main checkout's ``node_modules``. So
``remove_tree`` never recurses through a reparse point / symlink: when it meets
one it unlinks the LINK itself (leaving the target untouched) and only descends
into genuine directories.

``core/`` imports nothing project-level — this module is stdlib only.
"""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Optional


class OutsideOutputError(RuntimeError):
    """A path would resolve outside (or is not under) the Output_Directory.

    Raised by ``OutputRoot`` before any filesystem mutation, so existing output
    is never disturbed when a caller passes an escaping path (a ``..`` traversal
    or an absolute path elsewhere).
    """


def _resolve(p: Path) -> Path:
    """Resolve ``p`` without requiring it to exist (``strict=False``).

    ``Path.resolve`` collapses ``..`` segments and makes the path absolute; with
    ``strict=False`` it does so even for a path that does not exist yet (the
    common case — we check *before* creating the file).
    """
    return Path(p).resolve(strict=False)


class OutputRoot:
    """An output directory exposing only confinement-checked operations.

    Every method that writes, moves or removes first asserts the target path
    resolves inside ``self.root`` (via :meth:`path` / :meth:`contains`); an
    escaping path raises :class:`OutsideOutputError` and nothing happens.
    """

    def __init__(self, root: Path) -> None:
        self.root: Path = _resolve(Path(root))

    # -- containment -------------------------------------------------------

    def contains(self, p: Path) -> bool:
        """True iff the resolved ``p`` is the root itself or lies under it."""
        rp = _resolve(p)
        if rp == self.root:
            return True
        return self.root in rp.parents

    def path(self, *parts: str) -> Path:
        """Join ``parts`` under the root and assert containment.

        Returns the resolved absolute path when it is inside the root; raises
        :class:`OutsideOutputError` otherwise. ``parts`` are joined onto the
        root, so an absolute part or a ``..`` that escapes the root is caught.
        """
        joined = self.root.joinpath(*parts) if parts else self.root
        resolved = _resolve(joined)
        if not self.contains(resolved):
            raise OutsideOutputError(
                f"path {resolved} resolves outside output root {self.root}"
            )
        return resolved

    # -- checked mutations -------------------------------------------------

    def mkdir(self, *parts: str) -> Path:
        """Create a directory (with parents) under the root; return its path."""
        target = self.path(*parts)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def write_bytes(self, relpath: str, data: bytes) -> Path:
        """Write ``data`` to ``relpath`` under the root, creating parents."""
        target = self.path(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def write_text(self, relpath: str, text: str) -> Path:
        """Write ``text`` (UTF-8) to ``relpath`` under the root, creating parents."""
        target = self.path(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def replace(self, src: Path, dst: Path) -> Path:
        """``os.replace(src, dst)`` with BOTH paths confined to the root.

        Used for the Pipeline's atomic scratch-to-final move. Both endpoints are
        checked, so a move can neither read from nor write to outside the root.
        """
        s = self.path(str(src)) if not Path(src).is_absolute() else _checked(self, src)
        d = self.path(str(dst)) if not Path(dst).is_absolute() else _checked(self, dst)
        os.replace(str(s), str(d))
        return d

    def remove_tree(self, path: Path) -> None:
        """Remove ``path`` (a file or directory tree) confined to the root.

        NEVER recurses through a junction / symlink. On a reparse point or a
        symlink it unlinks the LINK itself (directory junction -> ``rmdir`` the
        link; symlink -> ``unlink``), leaving whatever the link points at
        untouched. Only genuine directories are descended into. Missing paths
        are a no-op.
        """
        target = _checked(self, path)
        _remove_tree_safe(target)


def _checked(root: OutputRoot, p: Path) -> Path:
    """Resolve ``p`` and assert it is inside ``root`` (or raise)."""
    resolved = _resolve(p)
    if not root.contains(resolved):
        raise OutsideOutputError(
            f"path {resolved} resolves outside output root {root.root}"
        )
    return resolved


def _is_link(p: Path) -> bool:
    """True if ``p`` is a symlink OR a Windows reparse point (e.g. a junction).

    ``Path.is_symlink`` catches symlinks on every platform but NOT a Windows
    directory junction (which is a reparse point, not a symlink). We also inspect
    ``st_file_attributes`` for ``FILE_ATTRIBUTE_REPARSE_POINT`` via ``lstat`` so a
    junction is recognised and never recursed through.
    """
    try:
        if p.is_symlink():
            return True
    except OSError:
        return False
    reparse = getattr(os.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    try:
        st = os.lstat(p)
    except OSError:
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & reparse)


def _unlink_as_link(p: Path) -> None:
    """Remove the link ``p`` itself without following it into its target.

    A directory junction / directory symlink is removed with ``os.rmdir`` (which
    unlinks the reparse point and does NOT touch the target); a file symlink with
    ``os.unlink``. Both operate on the link, never its contents.
    """
    try:
        os.rmdir(p)  # directory junction or directory symlink: unlink the link.
    except (NotADirectoryError, OSError):
        try:
            os.unlink(p)  # file symlink.
        except OSError:
            pass


def _remove_tree_safe(target: Path) -> None:
    """Recursively remove ``target``, treating links as leaves (unlink, no recurse)."""
    if not (target.exists() or target.is_symlink()):
        return  # nothing to do (and a broken symlink still reports is_symlink).

    if _is_link(target):
        _unlink_as_link(target)
        return

    if target.is_dir():
        for child in target.iterdir():
            _remove_tree_safe(child)
        try:
            target.rmdir()
        except OSError:
            pass
        return

    try:
        target.unlink()
    except OSError:
        pass


def assert_output_allowed(output_dir: Path, eq_path: Optional[Path]) -> None:
    """Refuse an output dir that would write into the EQ install (Req 10.2).

    Raises :class:`OutsideOutputError` if ``output_dir`` resolves to ``eq_path``,
    lies inside it, or *contains* it — any of which would let a build write into
    (or over) the EQ_PATH install. ``eq_path`` of ``None``/empty means EQ_PATH is
    unset: there is nothing to compare, so the check passes.
    """
    if eq_path is None or str(eq_path) == "":
        return
    out = _resolve(Path(output_dir))
    eq = _resolve(Path(eq_path))
    if out == eq or eq in out.parents or out in eq.parents:
        raise OutsideOutputError(
            f"output directory {out} overlaps the EQ install {eq}; "
            f"refusing to write into or over the EQ_PATH install"
        )


def new_zone_id(prefix: str = "gen") -> str:
    """A fresh zone id: ``<prefix>_<ts>_<hex6>`` (lowercase).

    ``<ts>`` is a unix-ish second timestamp and ``<hex6>`` six random hex chars,
    so two calls in the same second still differ. This is both the build
    directory name and (for the server) the Build_Name; the CLI passes a
    sanitised ``prefix`` (task 19.4).
    """
    ts = int(time.time())
    return f"{prefix}_{ts}_{secrets.token_hex(3)}".lower()
