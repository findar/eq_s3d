"""
tests/test_hygiene.py
---------------------
M0 hygiene guards (see `.kiro/specs/zone-generator-m0-hygiene/`).

This module currently holds the outdoor-TER fork-point baseline (task 4.1). The
cave/viewer residue guards (task 14.1) are appended here later.

Fork-point baseline — why it exists
====================================
The M0 milestone deletes the cave pipeline and the legacy viewer. Those deletions
touch shared modules (`generators/builder.py`, `generators/layout.py`,
`generators/field/noise.py`, ...) that the *outdoor* (heightfield) backend also
depends on. This test pins the exact bytes the outdoor TER builder produces on the
UNCHANGED fork-point geometry, so any accidental behavioural change from a deletion
shows up as a hard failure instead of slipping through.

Fork-point commit: 99d346a7ba65ce22c2559f43a2703ccb8ac0a313
  ("Add zone-generator umbrella spec and M0 milestone spec")

Capture procedure (one-off, NOT committed — run on the fork-point code, before any
task-5 deletion, in the pinned `-Venv` worktree):

    import hashlib, tempfile
    from generators.layout import LayoutGenerator
    from tests.pbt_helpers import build_raw
    for s in OUTDOOR_BASELINE_SEEDS:
        spec = LayoutGenerator("outdoor", seed=s).generate(f"ob{s}", room_count=6)
        with tempfile.TemporaryDirectory() as d:
            _, ter_bytes, _ = build_raw(spec, d)
        print(s, hashlib.sha256(ter_bytes).hexdigest())

A later MISMATCH is a bug in the deletion that changed outdoor geometry — it is
NEVER a reason to recapture these literals. Fix the deletion instead.

Caveat (design risk): these hashes were captured in the pinned `-Venv` on this
machine. The byte-exact TER output can move across numpy versions (float ordering
/ libm differences), so a mismatch after a numpy bump is a known, separate cause —
investigate the environment before suspecting the deletion in that case.
"""

from __future__ import annotations

import hashlib
import tempfile

import pytest

from generators.layout import LayoutGenerator
from tests.pbt_helpers import build_raw


OUTDOOR_BASELINE_SEEDS = (7, 1955208177, 2147483647)

# seed -> sha256(ter_bytes).hexdigest() captured on fork-point 99d346a7
OUTDOOR_BASELINE = {
    7: "b3a852e7aa944bb982cfb7c7811b227c55a65305559ee1c16c393e9295b2e80d",
    1955208177: "638272f9fc80a96d2e0ec6622c4bfd509e4c55d71c0c7736dfb8957fd05b5da1",
    2147483647: "e51045058d3b5b3141947588004eb45bd185edab28a7dec1b718ccde7786a1e7",
}


@pytest.mark.parametrize("seed", OUTDOOR_BASELINE_SEEDS)
def test_outdoor_ter_matches_fork_point(seed):
    """The outdoor TER builder reproduces its fork-point bytes exactly.

    A failure means an M0 deletion changed outdoor geometry — fix the deletion,
    do not recapture the literal (see module docstring).
    """
    spec = LayoutGenerator("outdoor", seed=seed).generate(f"ob{seed}", room_count=6)
    with tempfile.TemporaryDirectory() as d:
        _, ter_bytes, _ = build_raw(spec, d)
    got = hashlib.sha256(ter_bytes).hexdigest()
    assert got == OUTDOOR_BASELINE[seed], (
        f"outdoor TER for seed {seed} drifted from the fork-point baseline; "
        f"an M0 deletion likely changed outdoor geometry"
    )

# ======================================================================
# Residue guards (task 14.1)
# ======================================================================
# Static checks that lock in the cave-pipeline removal (tasks 5.x) and the
# legacy-viewer removal (task 6.x). They scan the tracked `*.py` source and a
# few non-Python surfaces (web/index.html, requirements.txt) for tokens that
# MUST be gone. A failure here means a prior deletion left residue behind — it
# is a real finding to escalate, NOT something this test module should "fix" by
# deleting code.
#
# This module is EXCLUDED from the scans (it necessarily names the forbidden
# tokens). To make that exclusion belt-and-suspenders, every forbidden token is
# built by string CONCATENATION below so this file never contains the literal
# token even as a byte sequence — a scanner that forgot to exclude us still
# wouldn't match.

import ast
import re
import subprocess
from pathlib import Path

# Repo root = parent of this tests/ directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_THIS_REL = "tests/test_hygiene.py"

# Forbidden tokens, assembled by concatenation so they don't appear literally
# in this file's own source.
_TOK_FBM = "fbm" + "_field"
_TOK_BUILD_ORGANIC = "_build" + "_organic"
_TOK_CAVE_THEMES = "_CAVE" + "_THEMES"
_TOK_SKIMAGE = "ski" + "mage"
_TOK_FAST_SIMPLIFY = "fast_" + "simplification"
_TOK_QUADRIC = "simplify_" + "quadric_decimation"
_TOK_FLASK = "fl" + "ask"
_TOK_VIEWER = "view" + "er"
_TOK_ARGS_PREVIEW = "args." + "preview"

# The deleted cave field modules (basename stems, built so the names below
# aren't a literal import line here).
_DELETED_FIELD_STEMS = ("ca" + "ve", "fea" + "tures", "me" + "sh", "s" + "df")

DEFINED_THEMES = {"dungeon", "city", "outdoor"}


def _tracked_py_files():
    """Tracked *.py paths (repo-relative, forward slashes), minus this module."""
    out = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = []
    for line in out.splitlines():
        rel = line.strip().replace("\\", "/")
        if not rel or rel == _THIS_REL:
            continue
        files.append(rel)
    return files


def _read(rel):
    return (_REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")


def _scan_token(token):
    """Return [(rel, lineno, line)] for every tracked .py containing `token`."""
    hits = []
    for rel in _tracked_py_files():
        for i, line in enumerate(_read(rel).splitlines(), start=1):
            if token in line:
                hits.append((rel, i, line.strip()))
    return hits


# ----------------------------------------------------------------------
# Cave-pipeline residue
# ----------------------------------------------------------------------

def test_deleted_field_modules_absent():
    """The four cave field modules must not exist."""
    for stem in _DELETED_FIELD_STEMS:
        p = _REPO_ROOT / "generators" / "field" / f"{stem}.py"
        assert not p.exists(), f"deleted cave field module reappeared: {p}"


def test_no_import_of_deleted_field_modules():
    """No tracked source imports the deleted cave field modules.

    Covers absolute (`generators.field.sdf`, `generators.field import sdf`) and
    relative (`from .sdf import ...`) forms, parsed via AST so comments and
    prose don't produce false positives.
    """
    offenders = []
    for rel in _tracked_py_files():
        src = _read(rel)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    tail = alias.name.rsplit(".", 1)[-1]
                    if tail in _DELETED_FIELD_STEMS and (
                        "field" in alias.name or alias.name in _DELETED_FIELD_STEMS
                    ):
                        offenders.append((rel, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                mod_tail = mod.rsplit(".", 1)[-1]
                # `from generators.field.sdf import X` / `from .sdf import X`
                if mod_tail in _DELETED_FIELD_STEMS and (
                    node.level > 0 or "field" in mod
                ):
                    offenders.append((rel, node.lineno, f"from {mod}"))
                # `from generators.field import sdf` / `from .field import sdf`
                if mod_tail == "field" or mod.endswith("field"):
                    for alias in node.names:
                        if alias.name in _DELETED_FIELD_STEMS:
                            offenders.append(
                                (rel, node.lineno, f"from {mod} import {alias.name}")
                            )
    assert not offenders, (
        "found imports of deleted cave field modules (prior deletion left "
        f"residue): {offenders}"
    )


def test_no_cave_pipeline_tokens():
    """No `fbm_field`, `_build_organic` or `_CAVE_THEMES` token survives."""
    for token in (_TOK_FBM, _TOK_BUILD_ORGANIC, _TOK_CAVE_THEMES):
        hits = _scan_token(token)
        assert not hits, (
            f"cave-pipeline token {token!r} still present (prior deletion left "
            f"residue): {hits}"
        )


def test_noise_keeps_value_noise_and_drops_sdf():
    """`generators/field/noise.py` defines `_value_noise_3d` and imports no sdf.

    Parsed via AST: the function must still be defined, and no import statement
    may reference the deleted `sdf` module (absolute or relative).
    """
    src = _read("generators/field/noise.py")
    tree = ast.parse(src)

    defines = {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_value_noise_3d" in defines, (
        "generators/field/noise.py must still define _value_noise_3d"
    )

    sdf_stem = "s" + "df"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.rsplit(".", 1)[-1] != sdf_stem, (
                    f"noise.py must not import {sdf_stem}: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod.rsplit(".", 1)[-1] != sdf_stem, (
                f"noise.py must not import from {sdf_stem}: from {mod}"
            )
            for alias in node.names:
                assert alias.name != sdf_stem, (
                    f"noise.py must not import {sdf_stem} name: {alias.name}"
                )


def _layout_dict_keys(var_name):
    """Collect the string keys of the (single) dict literal assigned to
    `var_name` anywhere in generators/layout.py, via AST."""
    tree = ast.parse(_read("generators/layout.py"))
    keysets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            if any(t.id == var_name for t in targets) and isinstance(
                node.value, ast.Dict
            ):
                keys = {
                    k.value
                    for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
                keysets.append(keys)
    return keysets


def test_layout_tables_have_no_cave_key():
    """LayoutGenerator's per-theme material and light tables drop `"cave"`.

    The tables are `theme_palettes` (materials) and `colors` (light colours);
    both are theme-keyed dicts whose keys must be exactly the Defined_Themes.
    """
    cave_key = "ca" + "ve"
    for var in ("theme_palettes", "colors"):
        keysets = _layout_dict_keys(var)
        assert keysets, f"could not find dict literal {var!r} in layout.py"
        for keys in keysets:
            assert cave_key not in keys, (
                f"layout.py {var!r} still has a {cave_key!r} key: {sorted(keys)}"
            )
            assert keys == DEFINED_THEMES, (
                f"layout.py {var!r} keys {sorted(keys)} != Defined_Themes "
                f"{sorted(DEFINED_THEMES)}"
            )


def test_no_cave_only_dependency_tokens():
    """No scikit-image / fast-simplification / quadric-decimation residue."""
    skimage_import = "import " + _TOK_SKIMAGE
    skimage_from = "from " + _TOK_SKIMAGE
    for token in (skimage_import, skimage_from, _TOK_FAST_SIMPLIFY, _TOK_QUADRIC):
        hits = _scan_token(token)
        assert not hits, (
            f"cave-only dependency token {token!r} still present: {hits}"
        )


# ----------------------------------------------------------------------
# Theme surface
# ----------------------------------------------------------------------

def test_theme_surface_is_three():
    """Every theme surface equals the Defined_Themes set.

    Checks `ai.schema.VALID_THEMES`, `server.app.VALID_THEMES`, the `main.py`
    `--theme` argparse choices and the `web/index.html` theme `<option>` values.
    """
    import ai.schema
    import server.app

    assert set(ai.schema.VALID_THEMES) == DEFINED_THEMES, (
        f"ai.schema.VALID_THEMES = {ai.schema.VALID_THEMES}"
    )
    assert set(server.app.VALID_THEMES) == DEFINED_THEMES, (
        f"server.app.VALID_THEMES = {server.app.VALID_THEMES}"
    )

    # main.py --theme choices: parse the argparse call from source (importing
    # main would execute CLI-construction code; reading the source is safe and
    # robust). Grab the choices=[...] list attached to the --theme argument.
    main_src = _read("main.py")
    m = re.search(r"--theme[\s\S]*?choices\s*=\s*\[([^\]]*)\]", main_src)
    assert m, "could not find --theme choices=[...] in main.py"
    theme_choices = set(re.findall(r"""['"]([^'"]+)['"]""", m.group(1)))
    assert theme_choices == DEFINED_THEMES, (
        f"main.py --theme choices = {sorted(theme_choices)}"
    )

    # web/index.html theme <option value="..."> values.
    html = _read("web/index.html")
    option_vals = set(re.findall(r'<option\s+value="([^"]+)"', html))
    assert option_vals == DEFINED_THEMES, (
        f"web/index.html theme <option> values = {sorted(option_vals)}"
    )


# ----------------------------------------------------------------------
# Legacy-viewer residue
# ----------------------------------------------------------------------

def test_viewer_directory_absent():
    """The legacy `viewer/` package must not exist."""
    assert not (_REPO_ROOT / _TOK_VIEWER).exists(), "legacy viewer/ reappeared"


def test_no_viewer_or_flask_imports():
    """No tracked source imports `flask` or the `viewer` package, and no
    `args.preview` token survives.

    Imports are checked via AST so the prose word "viewer" in comments/docstrings
    (which is fine) doesn't trip the guard — only an actual import of the
    `viewer` module or `flask` does.
    """
    import_offenders = []
    for rel in _tracked_py_files():
        src = _read(rel)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".", 1)[0]
                    if top in (_TOK_FLASK, _TOK_VIEWER):
                        import_offenders.append((rel, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    top = node.module.split(".", 1)[0]
                    if top in (_TOK_FLASK, _TOK_VIEWER):
                        import_offenders.append(
                            (rel, node.lineno, f"from {node.module}")
                        )
    assert not import_offenders, (
        f"found flask/viewer imports (prior deletion left residue): "
        f"{import_offenders}"
    )

    preview_hits = _scan_token(_TOK_ARGS_PREVIEW)
    assert not preview_hits, (
        f"{_TOK_ARGS_PREVIEW!r} token still present: {preview_hits}"
    )


# ----------------------------------------------------------------------
# Deleted test module + requirements.txt
# ----------------------------------------------------------------------

def test_test_cave_module_absent():
    """`tests/test_cave.py` must not exist."""
    name = "tests/test_" + "cave.py"
    assert not (_REPO_ROOT / name).exists(), f"{name} reappeared"


def test_requirements_clean_and_pins_hypothesis():
    """requirements.txt drops the cave/viewer deps and pins the test harness."""
    lines = _read("requirements.txt").splitlines()
    forbidden = {
        "scikit-image": "scikit" + "-image",
        "fast-simplification": "fast" + "-simplification",
        "flask": _TOK_FLASK,
    }
    for label, token in forbidden.items():
        for ln in lines:
            # Ignore comment-only lines; a dep line names the token at the start.
            code = ln.split("#", 1)[0].strip().lower()
            assert token not in code, (
                f"requirements.txt still lists {label!r}: {ln!r}"
            )
    hyp_pin = "hypothesis" + "=="
    assert any(
        ln.split("#", 1)[0].strip().lower().startswith(hyp_pin) for ln in lines
    ), "requirements.txt must pin hypothesis== (test harness)"
