"""
server/app.py
-------------
FastAPI backend that wraps the procedural generators for the browser UI.

The browser POSTs generation parameters (theme, room count, elevation) and
gets back a zone id. It then fetches the GLB and the zone.json sidecar to
render and walk the zone.

Randomness: every /generate call uses a fresh random seed unless the caller
explicitly pins one, so identical inputs still produce different zones.

Run:
    uvicorn server.app:app --reload --port 8000
or:
    python -m server.app
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from core.env import env_value
from core.paths import OutputRoot, assert_output_allowed, new_zone_id
from generators.builder import with_decor_layers
from generators.pipeline import generate_validated, GenerationFailed
from generators.zone_types import (
    DEFINED_ZONE_TYPES, DEFAULT_ZONE_TYPE, LANDSCAPE_ZONE_TYPES, canonical_zone_type,
    ENABLED_ZONE_TYPES, is_enabled, zone_type_listing,
)
from analyzer.style_builder import REFERENCE_ZONES
from ai.planner import make_plan, get_planner
from ai.expand import plan_to_spec
from ai.schema import (
    LAYOUT_ZONE_TYPES, VALID_DUNGEON_RACES, VALID_DUNGEON_THEMES, VALID_LAYOUTS,
    SCALE_CONTROLS, VALID_FEATURES, ZonePlan, available_overlays, available_rule_sets, available_wall_styles,
    scale_control, VALID_SITES, available_inhabitants,
    DECOR_ZONE_TYPES, DEFAULT_DECOR, VALID_DECOR, decor_seed, rooms_seed,
)

logger = logging.getLogger("eq_s3d.server")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).parent.parent
OUTPUT_DIR  = ROOT / "output" / "web"
WEB_DIST    = ROOT / "web" / "dist"      # built front-end (Vite build)
FAILURE_LOG = ROOT / "output" / "validation_failures.jsonl"  # triage feed

# Refusal (Req 10.2): BEFORE the OUTPUT_DIR is created, at IMPORT time, refuse
# an output directory that overlaps the EQ_PATH install — so importing
# ``server.app`` with an overlapping EQ_PATH raises ``OutsideOutputError`` and
# the server never starts (uvicorn fails to load the app). EQ_PATH unset (or
# non-overlapping) ⇒ the check passes and import proceeds normally.
assert_output_allowed(OUTPUT_DIR, env_value("EQ_PATH"))

# Create the output dir through an OutputRoot so the creation itself is
# confinement-checked (it is the root, so this is a plain mkdir of the root).
OutputRoot(OUTPUT_DIR).mkdir()

# The available zone types come from the single source of truth
# (generators/zone_types.py); the server no longer keeps its own list.
VALID_ZONE_TYPES = list(DEFINED_ZONE_TYPES)

# ---------------------------------------------------------------------------
# Per-build file serving (task 15.5)
# ---------------------------------------------------------------------------
#
# The pipeline (task 15.4) moves an accepted build's files into
# output/web/<zone_id>/v<version>/<zone_id>.*, with the EQ map files under its
# ``maps/`` subfolder (M2). The routes that serve them
# (`/api/zones/{zone_id}/{version}/{filename}` and `.../maps/{filename}`) are
# deliberately strict: each URL segment must match SEGMENT_RE and contain no
# `..`, the file extension must be in the Build_File_Allow_List for its folder,
# and the resolved path must still lie inside the build directory under
# OUTPUT_DIR — so no crafted segment can read outside the output tree.

# A single path segment: letters, digits, underscore, dot and hyphen only.
# Rejects `/`, `\`, drive letters; `..` (and a bare `.`) are refused separately.
SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# The Build_File_Allow_List, split by folder: the build dir root holds the
# archive, preview, sidecar and map SVG; ``maps/`` holds only the EQ map
# ``.txt`` files. Anything else (a stray ``.py``, ``.jsonl``, a ``.txt`` at the
# root) is refused before any file access.
BUILD_FILE_EXTS = (".eqg", ".glb", ".zone.json", ".map.svg", ".png", ".sql", ".zip")
MAPS_FILE_EXTS = (".txt",)
MAPS_SUBDIR = "maps"

# Final extension -> media type for the FileResponse.
_MEDIA_BY_EXT = {
    ".txt": "text/plain; charset=us-ascii",
    ".eqg": "application/octet-stream",
    ".svg": "image/svg+xml",
    ".glb": "model/gltf-binary",
    ".json": "application/json",
    ".png": "image/png",
    ".sql": "application/sql",
    ".zip": "application/zip",
}


def _file_extension(filename: str) -> str:
    """The final extension of ``filename``, lower-cased (the media-type key).

    Multi-dot names like ``gen_123.zone.json`` / ``gen_123.map.svg`` give
    ``.json`` / ``.svg``; the allow-list itself checks the double suffix.
    """
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _rooms(plan, rooms_seed):
    """``plan`` with the pipeline's rerolled rooms seed, if it drew one (task 19)."""
    import dataclasses
    return plan if rooms_seed is None else dataclasses.replace(plan, rooms_seed=rooms_seed)


def _safe_segment(seg: str) -> bool:
    """One URL segment is a single safe path component (Req 9.3). ``fullmatch``,
    not ``match``: ``$`` also matches before a trailing newline, so ``match``
    let ``gen_t\\n`` through to the filesystem."""
    return bool(SEGMENT_RE.fullmatch(seg)) and ".." not in seg and seg != "."

# ---------------------------------------------------------------------------
# Build identity (which code is this process actually running?)
# ---------------------------------------------------------------------------
#
# The server runs with reload=False, so edits/commits made after it started are
# NOT live until a restart. BUILD_INFO is captured once, at import (= process
# start); /api/version recomputes the same values per request and reports
# `stale` when they differ, so the web UI can warn instead of silently showing
# geometry from old code.

REPO_ROOT = Path(__file__).resolve().parent.parent   # works in worktrees too
# Python source the server imports; edits here change generated output.
SOURCE_DIRS = ("ai", "analyzer", "core", "generators", "server")
UNKNOWN = "unknown"


def _git(*args: str) -> Optional[str]:
    """Run a git command in the repo root; stripped stdout, or None on failure."""
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _current_commit() -> str:
    """Full HEAD commit hash right now ("unknown" without git)."""
    return _git("rev-parse", "HEAD") or UNKNOWN


def _source_fingerprint() -> str:
    """Short hash over (relative path, mtime_ns, size) of the server's .py source.

    Catches uncommitted edits made after startup, which a HEAD comparison alone
    misses. Stat-only (no file reads), so it's cheap enough per request.
    """
    h = hashlib.sha1()
    files = sorted(
        p for d in SOURCE_DIRS for p in (REPO_ROOT / d).rglob("*.py")
    )
    for p in files:
        try:
            st = p.stat()
        except OSError:
            continue  # vanished between glob and stat; skip it
        rel = p.relative_to(REPO_ROOT).as_posix()
        h.update(f"{rel}\0{st.st_mtime_ns}\0{st.st_size}\n".encode())
    return h.hexdigest()[:12]


def _capture_build_info() -> dict:
    commit = _current_commit()
    dirty_out = _git("status", "--porcelain", "--untracked-files=no")
    return {
        "commit": commit,
        "short": commit[:7] if commit != UNKNOWN else UNKNOWN,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or UNKNOWN,
        # Uncommitted changes to tracked files at startup (None -> no git).
        "dirty": bool(dirty_out) if dirty_out is not None else False,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_fingerprint": _source_fingerprint(),
    }


BUILD_INFO = _capture_build_info()

# ---------------------------------------------------------------------------
# Network binding (loopback only) and CORS
# ---------------------------------------------------------------------------

# The server binds the loopback interface only; it is never exposed off-box.
# HOST/PORT are module-level so the __main__ path is testable without a real
# bind (Req 9.1).
HOST = "127.0.0.1"
PORT = 8000

# Exactly the origins the browser front-end is served from. An explicit list
# (never "*") means Starlette echoes the request Origin only when it matches
# one of these, so credentials/other origins are never granted (Req 9.2-9.4).
WEB_APP_ORIGINS = (
    "http://127.0.0.1:8000", "http://localhost:8000",     # same-origin (web/dist)
    "http://localhost:5173", "http://127.0.0.1:5173",     # frontend port
)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Server startup: point process temp files at ``OUTPUT_DIR/.tmp`` (Req 10.1).

    Runs on the server's STARTUP path (when the ASGI server starts the app),
    never at import — so merely importing ``server.app`` (as the test suite
    does) does NOT mutate the global ``tempfile.tempdir`` and the suite's own
    temp dirs are untouched. The ``.tmp`` dir is confinement-checked and created
    through the OutputRoot.
    """
    import tempfile
    tempfile.tempdir = str(OutputRoot(OUTPUT_DIR).mkdir(".tmp"))
    yield


app = FastAPI(title="eq_s3d zone generator", version="0.3.0",
              lifespan=_lifespan)


class LocalCORSMiddleware(CORSMiddleware):
    """Explicit-origin CORS that also closes a stock-Starlette leak.

    Starlette's ``CORSMiddleware`` short-circuits every preflight (an OPTIONS
    with ``Access-Control-Request-Method``) into a canned 200 response whose
    ``Access-Control-Allow-*`` headers are precomputed and emitted *regardless*
    of whether the request Origin is actually allowed. That hands a disallowed
    origin a usable CORS grant on preflight. We override ``preflight_response``
    and strip every ``Access-Control-Allow-*`` header back off when the Origin
    isn't in the allow list, so a foreign preflight gets no grant (Req 9.3, 9.7).
    """

    def preflight_response(self, request_headers):
        resp = super().preflight_response(request_headers)
        if not self.is_allowed_origin(request_headers["origin"]):
            for k in [k for k in resp.headers
                      if k.lower().startswith("access-control-allow-")]:
                del resp.headers[k]
        return resp


# Loopback-only CORS: explicit origins, GET/POST, Content-Type only. No
# credentials and no exposed headers.
app.add_middleware(
    LocalCORSMiddleware,
    allow_origins=list(WEB_APP_ORIGINS),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def _validation_to_400(request: Request, exc: RequestValidationError):
    """Turn any ``/api/generate`` body-validation error into a 400 that names
    the offending field, instead of FastAPI's default raw 422 (Req 2.5).

    A ``StrictInt`` field fed a float/bool/string, or any other schema error on
    the generate body, surfaces as ``"<field> must be an integer"`` (for the
    integer fields) or ``"<field>: <message>"`` — always a 400 naming the field
    (``loc[-1]``), never a 422. Other routes keep FastAPI's default handling.
    """
    if not request.url.path.startswith(("/api/generate", "/api/rebuild")):
        # Preserve the default 422 for every other route.
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    errors = exc.errors()
    detail = "invalid request"
    if errors:
        err = errors[0]
        loc = err.get("loc", ())
        field = str(loc[-1]) if loc else "body"
        # The StrictInt fields (seed, rooms) read most clearly as "must be an
        # integer"; everything else keeps the validator's own message.
        if field in ("seed", "decor_seed", "rooms_seed", "rooms", "room_count", "locks"):
            detail = f"{field} must be an integer"
        else:
            detail = f"{field}: {err.get('msg', 'invalid value')}"
    return JSONResponse(status_code=400, content={"detail": detail})


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

# The Pinned_Seed domain: a 32-bit non-negative integer (Req 2.5). A pinned seed
# outside this range is a 400 naming ``seed``.
SEED_MIN = 0
SEED_MAX = 2_147_483_647

# The integer kinds the controls dict may NOT carry for its numeric fields. A
# JSON ``bool`` is an ``int`` subclass in Python, so it must be rejected
# explicitly; floats, strings, lists and null are rejected as non-int kinds.
VALID_MODES = ("prompt", "controls")


def _require_int(d: dict, key: str) -> None:
    """Reject a controls value that is present but not a JSON integer.

    Mirrors the ``StrictInt`` guard the top-level fields get from pydantic: a
    ``bool`` (an ``int`` subclass in Python), ``null`` and any other non-int
    kind (float, string, list) raise an :class:`HTTPException` 400 that names
    the field, so a malformed ``controls.room_count`` / ``controls.locks`` is a
    400 — never a silent coercion, never a downstream ``int(None)`` crash, and
    never a raw 422 (Req 2.5). An ABSENT key (not in ``d``) is fine: the plan
    default fills it. A present ``null`` is NOT absent — it is a supplied
    non-integer value and is refused, because ``ZonePlan.validate`` would other-
    wise ``int(None)`` on it and 500.
    """
    if key not in d:
        return
    v = d[key]
    if v is None or isinstance(v, bool) or not isinstance(v, int):
        raise HTTPException(400, f"{key} must be an integer")


def _require_edges(c: dict[str, Any], zone_type: Optional[str]) -> Optional[dict]:
    """Pop and validate ``controls.edges`` (the wilderness Rim declaration).

    Absent -> ``None`` (every side mountain). Present on a zone type with no
    landscape (not wilderness or outdoor_dungeon), not an object, or naming an
    unknown side/type -> a 400 that names the field, before any build or write
    (the M1 controls convention).
    """
    if "edges" not in c:
        return None
    raw = c.pop("edges")
    if raw is None:
        return None
    if zone_type not in LANDSCAPE_ZONE_TYPES:
        raise HTTPException(
            400, "edges only applies to zone_type wilderness or outdoor_dungeon")
    if not isinstance(raw, dict):
        raise HTTPException(
            400, "edges must be an object mapping a side (N/E/S/W) to "
                 "mountain, river or zoneline")
    from generators.wilderness.build import normalise_edges
    try:
        return normalise_edges(raw)
    except ValueError as exc:
        raise HTTPException(400, f"edges: {exc}")


def _require_trees(c: dict[str, Any], zone_type: Optional[str]) -> Optional[str]:
    """Pop and validate ``controls.trees`` (the wilderness Density_Level).

    Absent -> ``None`` (the prompt or the default decides). Present on a zone
    type with no landscape, or not one of the four levels -> a 400 that names
    the field, before any build or write (mirrors :func:`_require_edges`).
    """
    if "trees" not in c:
        return None
    raw = c.pop("trees")
    if raw is None:
        return None
    if zone_type not in LANDSCAPE_ZONE_TYPES:
        raise HTTPException(
            400, "trees only applies to zone_type wilderness or outdoor_dungeon")
    from generators.vegetation.kit import DENSITY_LEVELS
    if raw not in DENSITY_LEVELS:
        raise HTTPException(
            400, f"trees must be one of {', '.join(DENSITY_LEVELS)}")
    return raw


def _require_sites(c: dict[str, Any], zone_type: Optional[str]) -> Optional[str]:
    """Validate ``controls.sites`` / ``controls.inhabitant`` (step 10) in place.

    Absent or ``null`` -> the plan default (Sites normal, the biome's mix).
    Present on a zone type with no landscape, or not an allowed value -> a 400
    that names the field, before any build or write (as ``trees``). Returns
    ``"controls"`` when either was given (the sidecar's ``control_source``),
    else ``None``.
    """
    given = None
    for key, allowed, blank in (("sites", VALID_SITES, ""),
                                ("inhabitant", available_inhabitants(), " (or \"\" for the biome's mix)")):
        if key not in c:
            continue
        raw = c[key]
        if raw is None:
            c.pop(key)
            continue
        if zone_type not in LANDSCAPE_ZONE_TYPES:
            raise HTTPException(
                400, f"{key} only applies to zone_type wilderness or outdoor_dungeon")
        value = raw.strip().lower() if isinstance(raw, str) else None
        if value is None or (value not in allowed and not (blank and value == "")):
            raise HTTPException(400, f"{key} must be one of {', '.join(allowed)}{blank}")
        c[key] = value
        given = "controls"
    return given


def _require_stage_seed(c: dict[str, Any], key: str, top_seed: Optional[int],
                        check: Callable[[Any], Optional[int]]) -> None:
    """Validate a stage seed in the controls (``decor_seed``, ``rooms_seed``) in place,
    before any build or write. The request's top-level field of the same name (what
    "Reroll decor" / "Reroll rooms" send, in either mode) fills one the controls don't
    give; ``null`` is unset (the zone's seed stands in); anything but a whole
    0..2^31-1 is a 400 naming ``key``."""
    if c.get(key) is None and top_seed is not None:
        c[key] = top_seed
    if key in c and c[key] is None:
        c.pop(key)
    if key in c:
        try:
            c[key] = check(c[key])
        except ValueError:
            raise HTTPException(400, f"{key} must be an integer between {SEED_MIN} and {SEED_MAX}")


def _require_decor(c: dict[str, Any], zone_type: Optional[str],
                   top_seed: Optional[int] = None) -> None:
    """Validate ``controls.decor`` / ``controls.decor_seed`` (room-decor
    Req 10.1, 10.2) in place, before any build or write.

    Absent, ``null`` or ``decor: ""`` -> the default (normal; the zone's seed
    salts the Props). The request's top-level ``decor_seed`` (what "Reroll
    decor" sends, in either mode) fills a ``controls.decor_seed`` that isn't
    given. A value outside ``VALID_DECOR`` or a seed outside 0..2^31-1 is a 400
    naming the field; either on a zone type without rooms (wilderness) is a
    400, as ``sites`` is on a type without a landscape.
    """
    _require_stage_seed(c, "decor_seed", top_seed, decor_seed)
    if c.get("decor") is None:
        c.pop("decor", None)
    if "decor" in c:
        raw = c["decor"]
        value = raw.strip().lower() if isinstance(raw, str) else None
        if value is None or (value and value not in VALID_DECOR):
            raise HTTPException(400, f"decor must be one of {', '.join(VALID_DECOR)} "
                                     f"(or \"\" for the default, {DEFAULT_DECOR})")
        c["decor"] = value
    if zone_type not in DECOR_ZONE_TYPES:
        for key in ("decor", "decor_seed"):
            if c.get(key) not in (None, ""):
                raise HTTPException(400, f"{key} only applies to zone_type dungeon, city or outdoor_dungeon")


def _require_layout(c: dict[str, Any], zone_type: Optional[str]) -> None:
    """Validate ``controls.layout`` / ``controls.rule_set`` (graph-layout
    Req 7.1) in place, before any build or write.

    Absent or ``null`` -> the plan default (graph on a dungeon / outdoor
    dungeon since task 21, the theme's set; classic, ignored, elsewhere). A value
    that isn't one of ``VALID_LAYOUTS`` / ``available_rule_sets()`` is a 400
    naming the allowed values. Asking for a graph layout or a rule set on a
    zone type that doesn't take them (not dungeon or outdoor_dungeon) is a
    400, as ``edges`` / ``trees`` are on a type with no landscape; the default
    ``classic`` / ``""`` is accepted there, since it changes nothing.
    """
    for key in ("layout", "rule_set", "walls", "features", "overlay") + SCALE_CONTROLS:
        if key in c and c[key] is None:
            c.pop(key)
    layout = c.get("layout")
    if layout is not None:
        if not isinstance(layout, str) or layout.strip().lower() not in VALID_LAYOUTS:
            raise HTTPException(
                400, f"layout must be one of {', '.join(VALID_LAYOUTS)}")
        layout = c["layout"] = layout.strip().lower()
    rule_set = c.get("rule_set")
    if rule_set is not None:
        sets = available_rule_sets()
        if not isinstance(rule_set, str) or (rule_set.strip()
                                             and rule_set.strip() not in sets):
            raise HTTPException(
                400, f"rule_set must be one of {', '.join(sets)} "
                     "(or \"\" for the theme's set)")
        rule_set = c["rule_set"] = rule_set.strip()
    walls = c.get("walls")
    if walls is not None:
        styles = available_wall_styles()
        if not isinstance(walls, str) or (walls.strip().lower()
                                          and walls.strip().lower() not in styles):
            raise HTTPException(
                400, f"walls must be one of {', '.join(styles)} "
                     "(or \"\" for the theme's style)")
        walls = c["walls"] = walls.strip().lower()
    features = c.get("features")
    if features is not None:
        if not isinstance(features, str) or features.strip().lower() not in VALID_FEATURES:
            raise HTTPException(400, f"features must be one of {', '.join(VALID_FEATURES)}")
        features = c["features"] = features.strip().lower()
    leans = []
    for name in SCALE_CONTROLS:
        if name in c:
            try:
                c[name] = scale_control(name, c[name])
            except ValueError as exc:
                raise HTTPException(400, str(exc))
            if c[name] is not None:
                leans.append(name)
    overlay = c.get("overlay")
    if overlay is not None:
        overlays = available_overlays()
        if not isinstance(overlay, str) or (overlay.strip().lower() and overlay.strip().lower() not in overlays):
            raise HTTPException(400, f"overlay must be one of {', '.join(overlays)} (or \"\" for the rules alone)")
        overlay = c["overlay"] = overlay.strip().lower()
        if overlay:
            leans.append("overlay")
    if zone_type not in LAYOUT_ZONE_TYPES:
        if leans:
            raise HTTPException(400, f"{leans[0]} only applies to zone_type dungeon or outdoor_dungeon")
        if features and features != "normal":
            raise HTTPException(
                400, "features only applies to zone_type dungeon or outdoor_dungeon")
        if layout == "graph":
            raise HTTPException(
                400, "layout only applies to zone_type dungeon or outdoor_dungeon")
        if rule_set:
            raise HTTPException(
                400, "rule_set only applies to zone_type dungeon or outdoor_dungeon")
        if walls:
            raise HTTPException(
                400, "walls only applies to zone_type dungeon or outdoor_dungeon")


# The zone types a dungeon theme / race reaches: the room-graph types. A
# dungeon and a city go through the semantic layer in LayoutGenerator
# (generators/layout.py _SEMANTIC_ZONE_TYPES); an outdoor dungeon lays out its
# rooms as a dungeon (generators/outdoor_dungeon.py) and keeps both. A
# wilderness has no rooms, so neither means anything there.
CONTENT_ZONE_TYPES = ("dungeon", "city", "outdoor_dungeon")

# controls key -> its allowed values (ai/schema.py).
_CONTENT_CONTROLS = {
    "dungeon_theme": VALID_DUNGEON_THEMES,
    "dungeon_race": VALID_DUNGEON_RACES,
}


def _require_content(c: dict[str, Any], zone_type: Optional[str]) -> None:
    """Validate ``controls.dungeon_theme`` / ``controls.dungeon_race`` in place,
    before any build or write (graph-layout task 14).

    Absent, ``null`` or ``""`` -> none. Any other value must be one of the
    schema's list (case and surrounding space ignored), else a 400 naming the
    allowed values; ``ZonePlan.validate`` would otherwise drop it silently and
    build an unthemed zone. A theme or race on a zone type outside
    ``CONTENT_ZONE_TYPES`` is a 400, as ``layout: graph`` is on a type with no
    layout; ``""`` is accepted there, since it changes nothing.
    """
    for key, allowed in _CONTENT_CONTROLS.items():
        if key not in c:
            continue
        raw = c[key]
        if raw is None:
            c.pop(key)
            continue
        value = raw.strip().lower() if isinstance(raw, str) else None
        if value is None or (value and value not in allowed):
            raise HTTPException(
                400, f"{key} must be one of {', '.join(allowed)} "
                     "(or \"\" for none)")
        c[key] = value
        if value and zone_type not in CONTENT_ZONE_TYPES:
            raise HTTPException(
                400, f"{key} only applies to zone_type "
                     f"{', '.join(CONTENT_ZONE_TYPES[:-1])} or {CONTENT_ZONE_TYPES[-1]}")


class GenerateRequest(BaseModel):
    # An extra/unknown key (e.g. a legacy ``target_shortname``) is ignored like
    # any other non-field key rather than rejected (Req 8.1).
    model_config = ConfigDict(extra="ignore")

    # Explicit mode selector. When absent the mode is inferred from the presence
    # of ``prompt`` vs ``controls`` (see ``generate``). "prompt" | "controls".
    mode: Optional[str] = Field(default=None, description="prompt | controls")

    # If the resolved mode is ``prompt``, the planner derives zone_type/rooms/etc.
    # from ``prompt``. In ``controls`` mode the ``controls`` sub-object (or the
    # legacy flat fields) drive it.
    prompt: Optional[str] = Field(default=None, description="Natural-language prompt")
    controls: Optional[dict[str, Any]] = Field(
        default=None,
        description="Controls sub-object: zone_type, room_count, size, "
                    "verticality, locks, edges (wilderness Rim, e.g. "
                    "{\"N\": \"zoneline\"}), trees (wilderness density: "
                    "none/sparse/normal/dense), sites (none/sparse/normal/dense) "
                    "and inhabitant (human/orc/gnoll/centaur, \"\" for the "
                    "biome's mix; wilderness and outdoor_dungeon only), layout (classic/graph) and "
                    "rule_set (a base set, \"\" for the theme's) and walls (a wall style, "
                    "\"\" for the theme's) and features (none, sparse, normal, dense), and finish, "
                    "structure and clutter (0-10, or \"\" for the rules alone) and overlay; dungeon and "
                    "outdoor_dungeon only), dungeon_theme and dungeon_race "
                    "(\"\" for none; dungeon, city and outdoor_dungeon "
                    "only), decor (none/sparse/normal/dense, \"\" for normal) and "
                    "decor_seed (dungeon, city and outdoor_dungeon only), decor_layers "
                    "(decor layers on top of the dungeon theme's, from /api/controls), rooms_seed "
                    "(the rooms and Sites; every zone type), …",
    )
    # ``seed`` is StrictInt so a float/bool/string is a validation error (-> 400
    # via the RequestValidationError handler), never a silent coercion.
    seed: Optional[StrictInt] = Field(
        default=None, description="Pin a seed (omit for random)")
    # Rerolls the Props alone (room-decor Req 10.2), in either mode: "Reroll
    # decor" resends the last request with ``seed`` pinned and a fresh one.
    decor_seed: Optional[StrictInt] = Field(
        default=None, description="Decor seed: reroll the Props alone (omit for the zone's seed)")
    # Rerolls the rooms and Sites on the same World (world-sockets Req 4.1), in
    # either mode: "Reroll rooms" resends the last request with ``seed`` pinned
    # and a fresh one. The World is re-derived from ``seed``; nothing is read back.
    rooms_seed: Optional[StrictInt] = Field(
        default=None, description="Rooms seed: reroll the rooms and Sites on the same World "
                                  "(omit for the zone's seed)")

    # Legacy flat fields (mode absent -> inferred), kept for back-compat with
    # pre-mode clients. ``zone_type`` is preferred over the legacy ``theme``;
    # both are mapped forward (Req 11.1, 11.2). ``rooms`` is StrictInt so a
    # non-integer is a 400, not a clamp.
    zone_type: Optional[str] = Field(
        default=None, description="Legacy flat zone type (controls mode)")
    theme: Optional[str] = Field(
        default=None, description="Legacy alias for zone_type (deprecated)")
    rooms: Optional[StrictInt] = Field(
        default=None, description="Legacy flat room count (controls mode)")
    elevation: Optional[bool] = Field(
        default=None, description="Legacy flat multi-level flag (controls mode)")


class ArtifactRef(BaseModel):
    """One file of an accepted build, as the Artifacts_Panel lists it."""
    kind: str                        # "map_svg" | "eqmap" | "eqg" | "glb" | "sidecar"
    filename: str                    # relative to the build dir ("maps/<name>_1.txt")
    url: str                         # the build-file route that serves it
    layer: Optional[int] = None      # eqmap only: 0 = main band, 1..3


class GenerateResponse(BaseModel):
    id: str                          # the Build_Name (directory + file stem)
    version: int = 1                 # the per-build version (output/<id>/v<version>/)
    mode: str                        # the resolved mode: "prompt" | "controls"
    zone_type: str
    rooms: int
    seed: int
    vertices: int
    polygons: int
    materials: int
    glb_url: str
    zone_url: str
    map_url: str
    eqg_url: str = ""
    # Every file the build actually wrote, with its URL (M2 Req 9.5).
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    # What drove the generation (so the UI can show inferred choices). ``source``
    # is kept as a back-compat mirror of ``mode`` for pre-mode clients.
    source: str                      # "prompt" | "controls" (== mode)
    planner: Optional[str] = None    # "rule" | "llm" when a prompt was used
    plan: Optional[dict] = None      # the ZonePlan the planner produced
    gates: int = 0                   # number of lock-and-key gates (keyed dungeon)
    # Traversability gate provenance (see generators/pipeline.py).
    validated: bool = False          # did the traversability gate run AND pass?
    attempts: int = 1                # builds it took (fresh-seed retries on failure)
    # Non-fatal advisories for the UI: e.g. ``zone_type_substituted:<planned>->
    # dungeon`` when a prompt planned a disabled zone type, or a
    # ``backend_fallback`` note from the builder (Req 3.3).
    warnings: list[str] = Field(default_factory=list)
    # Whether the build cleared the Format_Checker (a passing stub until the
    # wave-6 rof2check lands).
    format_passed: bool = False
    # Short commit of the code this server process loaded (BUILD_INFO), so a
    # result/screenshot can be traced to the exact code that produced it.
    build_commit: str = UNKNOWN


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _zone_type_listing() -> dict:
    """Body shared by ``/api/zone_types`` and the legacy ``/api/themes`` alias.

    ``zone_types`` is the richer availability listing from
    ``generators/zone_types.py`` (one ``{name, enabled, reason}`` object per
    Defined zone type, in canonical order), not a bare name list — so the
    Web_App can render disabled options with their reason (Req 3.1, 3.2). Both
    endpoints return this exact body, so the legacy ``/api/themes`` alias stays
    byte-for-byte equal to ``/api/zone_types`` (Req 11.4).
    """
    return {
        "zone_types": zone_type_listing(),
        "default": DEFAULT_ZONE_TYPE,
        "reference_zones": {k: v for k, v in REFERENCE_ZONES.items()},
    }


def _enabled_zone_type_names() -> str:
    """Comma-separated enabled zone types in canonical order (for 400 detail)."""
    return ", ".join(
        zt["name"] for zt in zone_type_listing() if zt["enabled"]
    )


@app.get("/api/zone_types")
def list_zone_types():
    """Available zone types and the reference zones each profile was built from."""
    return _zone_type_listing()


@app.get("/api/themes")
def list_themes():
    """Legacy alias of ``/api/zone_types`` (same body)."""
    return _zone_type_listing()


@app.get("/api/controls")
def list_controls():
    """The values the page's control lists offer, from the code that checks
    them, so the page hard-codes none (room-decor Req 10.1). ``decor``:
    ``values`` in order, the ``default`` and the ``zone_types`` it applies to.
    ``decor_layers``: each decor layer in ``rules/decor/layers/`` with its
    description, read from the folder on every call, so a dropped-in file shows
    up without a restart (decor-rules Req 2.3)."""
    from ai import schema
    from generators.decor.rules import layer_names
    return {
        "decor": {"values": list(VALID_DECOR), "default": DEFAULT_DECOR,
                  "zone_types": list(DECOR_ZONE_TYPES)},
        "decor_layers": [{"name": name, "description": desc}
                         for name, desc in layer_names(schema.RULES_DECOR_DIR).items()],
    }


def _resolve_mode(req: GenerateRequest) -> str:
    """Resolve the request's mode BEFORE any build or write (Req 1.1, 1.3).

    An explicit ``mode`` wins and must be one of ``VALID_MODES`` (else 400).
    When absent, infer: a non-empty ``prompt`` means ``prompt`` mode; otherwise
    ``controls`` mode (the on-load / dropdown path).
    """
    if req.mode is not None:
        if req.mode not in VALID_MODES:
            raise HTTPException(
                400, f"mode must be one of: {', '.join(VALID_MODES)}")
        return req.mode
    return "prompt" if (req.prompt or "").strip() else "controls"


@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    # The zone id is both the per-build directory and the Build_Name on the
    # Server (design "Server"). Drawn from the shared ``new_zone_id`` helper
    # (``gen_<ts>_<hex6>``, lowercase) so the CLI and Server share one id shape
    # and one home for it (task 19.3 / 19.4).
    return _generate(req, new_zone_id(), 1)


def _saved_request(req: GenerateRequest, mode: str) -> dict:
    """The request as ``<name>.request.json`` keeps it (partial-rebuild Req 1.4), before the
    pipeline adds the seeds it built with: the body's fields, with ``controls`` as sent but
    for its stage seeds (the pipeline writes the resolved ones at the top level, where a
    resend applies them the same way)."""
    body = req.model_dump(exclude_none=True)
    body["mode"] = mode
    if "controls" in body:
        body["controls"] = {k: v for k, v in body["controls"].items()
                            if k not in ("decor_seed", "rooms_seed")}
    return body


def _generate(req: GenerateRequest, zone_id: str, version: int, *,
              saved: Optional[dict] = None,
              version_meta: Optional[dict] = None,
              partial: Optional[tuple] = None) -> GenerateResponse:
    """Generate (``version`` 1 of a new ``zone_id``) or a rebuild (the next version of an
    existing zone; ``saved`` is the request it is built from, its parent's ``request.json``
    with the change applied). A prompt-mode rebuild takes the plan the parent's planner
    produced from ``saved``: the planner is never called again. ``partial`` is a partial
    rebuild's ``(parent_dir, changes)``: the request is handled as here (its warnings, plan
    and saved request), and the zone is built from the parent's saved stages
    (``generators.rebuild.rebuild_decor``) instead of planned again."""
    # --- Mode + seed resolution: every 400 here happens BEFORE any build/write.
    mode = _resolve_mode(req)

    # A pinned seed must be in the 32-bit non-negative Pinned_Seed domain. (Its
    # integer *kind* is already guaranteed by StrictInt via the 400 handler.)
    if req.seed is not None and not (SEED_MIN <= req.seed <= SEED_MAX):
        raise HTTPException(
            400, f"seed must be between {SEED_MIN} and {SEED_MAX}")
    if req.decor_seed is not None and not (SEED_MIN <= req.decor_seed <= SEED_MAX):
        raise HTTPException(
            400, f"decor_seed must be between {SEED_MIN} and {SEED_MAX}")
    if req.rooms_seed is not None and not (SEED_MIN <= req.rooms_seed <= SEED_MAX):
        raise HTTPException(
            400, f"rooms_seed must be between {SEED_MIN} and {SEED_MAX}")

    plan_dict = None
    planner_name = None
    warnings: list[str] = []
    planned_zone_type: Optional[str] = None

    if mode == "prompt":
        # Prompt-driven: the planner derives the full spec. A missing/blank
        # prompt in prompt mode is a 400 before any build (Req 1.3). The plan is
        # seed-independent (it comes from the prompt), so build it once and let
        # the pipeline re-run spec expansion per fresh-seed retry.
        prompt = (req.prompt or "").strip()
        if not prompt:
            raise HTTPException(400, "a description is required for mode=prompt")
        replan = saved is not None and isinstance(saved.get("plan"), dict)
        if replan:
            # A rebuild: the parent's plan as it was built (named, substituted,
            # canonical), so the planner isn't asked again.
            planner_name = saved.get("planner")
            plan = ZonePlan.from_dict(saved["plan"])
            planned_zone_type = saved.get("planned_zone_type")
            if planned_zone_type is not None:
                warnings.append(
                    f"zone_type_substituted:{planned_zone_type}->{plan.zone_type}")
        else:
            planner_name = get_planner().name
            plan = make_plan(prompt, name=zone_id)
        # Guard the Build_Name: no planner output chooses the directory/file stem.
        plan.name = zone_id

        # A prompt-planned DISABLED zone type is not refused — it is substituted
        # to dungeon so the prompt still yields a zone, with a
        # ``zone_type_substituted:<planned>->dungeon`` warning for the UI and the
        # planned zone type recorded in the Sidecar (Req 3.3). A rebuild's saved
        # plan was substituted when it was planned.
        if not replan and not is_enabled(plan.zone_type):
            planned_zone_type = plan.zone_type
            plan.zone_type = DEFAULT_ZONE_TYPE
            # The plan's layout was resolved for the planned type; re-resolve
            # it for the substitute so it gets the new-request default too
            # (a prompt plan names no layout, graph-layout task 21).
            if planned_zone_type not in LAYOUT_ZONE_TYPES:
                plan.layout = ""
                plan.validate()
            warnings.append(
                f"zone_type_substituted:{planned_zone_type}->{DEFAULT_ZONE_TYPE}"
            )
        else:
            # The planned type is enabled: canonicalise it so a legacy value
            # (e.g. ``outdoor``) builds as its current name, mirroring the
            # controls path. The built/returned zone_type is always a canonical
            # member of the Enabled set.
            plan.zone_type = canonical_zone_type(plan.zone_type)

        # The plan as planned, before this request's stage seeds: what a rebuild
        # starts from (``request.json``), so a seed it names replaces this one's.
        saved_plan = plan.to_dict()
        # A decor seed rerolls the Props of whatever the prompt planned (a
        # wilderness has none, so it changes nothing there).
        if req.decor_seed is not None:
            plan.decor_seed = req.decor_seed
        # A rooms seed rerolls its rooms and Sites on the same World.
        if req.rooms_seed is not None:
            plan.rooms_seed = req.rooms_seed
        plan_dict = plan.to_dict()
        zone_type = plan.zone_type
        rooms = plan.room_count

        def factory(s: int, rooms_seed: Optional[int] = None):
            # ``rooms_seed`` is the pipeline's rooms reroll on a gate failure (task 19).
            return plan_to_spec(_rooms(plan, rooms_seed), seed=s)
    else:
        # Control-driven: the ``controls`` sub-object drives it, with the legacy
        # flat fields filling any key it doesn't name. The raw zone type is
        # checked against the Enabled set FIRST — before ``from_controls``
        # normalisation — so an undefined name like ``cave`` (canonicalises to
        # None) and the DISABLED ``wilderness`` are refused HTTP 400 BEFORE any
        # build or write, listing the enabled set (Req 3.3, matches 15.5).
        c: dict[str, Any] = dict(req.controls or {})
        # Legacy flat fields fill missing keys only (a controls key wins).
        if "zone_type" not in c and "theme" not in c:
            if req.zone_type is not None:
                c["zone_type"] = req.zone_type
            elif req.theme is not None:
                c["theme"] = req.theme
        if "room_count" not in c and "rooms" not in c and req.rooms is not None:
            c["rooms"] = req.rooms
        if "elevation" not in c and req.elevation is not None:
            c["elevation"] = req.elevation

        # Integer-kind guard for the controls numeric fields (float/bool/string/
        # list/null -> 400 naming the field, before any build).
        _require_int(c, "room_count")
        _require_int(c, "rooms")
        _require_int(c, "locks")

        # Raw zone type -> Enabled-set check BEFORE normalisation (15.5 behaviour).
        raw_zone_type = c.get("zone_type", c.get("theme"))
        if raw_zone_type is None:
            raw_zone_type = DEFAULT_ZONE_TYPE
        if not is_enabled(raw_zone_type):
            raise HTTPException(
                400,
                f"zone_type {raw_zone_type!r} is not available; enabled: "
                f"{_enabled_zone_type_names()}",
            )

        # The wilderness Rim rides in the controls but isn't a plan field, so
        # it is taken out (and validated) before from_controls sees the dict.
        edges = _require_edges(c, canonical_zone_type(raw_zone_type))
        trees = _require_trees(c, canonical_zone_type(raw_zone_type))
        sites_source = _require_sites(c, canonical_zone_type(raw_zone_type))
        _require_layout(c, canonical_zone_type(raw_zone_type))
        _require_content(c, canonical_zone_type(raw_zone_type))
        _require_decor(c, canonical_zone_type(raw_zone_type), req.decor_seed)
        _require_stage_seed(c, "rooms_seed", req.rooms_seed, rooms_seed)

        # Proven equal to the legacy LayoutGenerator path by the 17.4 golden test.
        # ``validate()`` raises ValueError on a value it refuses (an unknown
        # layout or rule set): a bad request, not a server fault.
        try:
            plan = ZonePlan.from_controls(c, warnings)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        plan.name = zone_id
        plan_dict = plan.to_dict()
        saved_plan = plan_dict
        zone_type = plan.zone_type
        rooms = plan.room_count

        def factory(s: int, rooms_seed: Optional[int] = None):
            return with_decor_layers(
                plan_to_spec(_rooms(plan, rooms_seed), seed=s, edges=edges, trees=trees,
                             trees_source="controls", sites_source=sites_source),
                plan.decor_layers)

    # Build + traversability gate. On gated themes a failing dungeon seed is
    # never returned: the pipeline retries on fresh seeds (bounded by attempts +
    # timeout) and returns the first passing zone, or raises GenerationFailed.
    request = {**_saved_request(req, mode), "plan": saved_plan, "planner": planner_name,
               **({"planned_zone_type": planned_zone_type} if planned_zone_type else {})}
    pipeline = dict(
        zone_type=zone_type,
        zone_id=zone_id,
        seed=req.seed,
        output_dir=OUTPUT_DIR,
        version=version,
        write_glb=True,
        failure_log=FAILURE_LOG,
        warnings=warnings,
        planned_zone_type=planned_zone_type,
        mode=mode,
        request=request,
        version_meta=version_meta,
    )
    try:
        if partial is not None:
            from generators.rebuild import rebuild_decor
            parent_dir, changes = partial
            vb = rebuild_decor(parent_dir, changes, generate=generate_validated, **pipeline)
        else:
            vb = generate_validated(factory, **pipeline)
    except GenerationFailed as e:
        # Exhaustion / pinned-seed failure -> clean error, never a broken GLB.
        raise HTTPException(
            503,
            detail=(
                "Couldn't produce a valid zone (every room reachable on foot) "
                f"within budget after {e.attempts} attempt(s). Please try again"
                + ("." if not e.pinned else
                   " with a different seed, or omit the seed to let the "
                   "generator find a valid one.")
            ),
        )

    result = vb.result
    if result.glb_path is None:
        raise HTTPException(500, "GLB export failed (is trimesh installed?)")

    # Accepted builds now live in a per-build directory
    # (output/web/<zone_id>/v1/<zone_id>.*, task 15.4), so the response URLs
    # point at the per-build route. The pipeline may have appended its own
    # advisories (e.g. a builder backend_fallback) to ``vb.warnings``; return
    # that merged list.
    base = f"/api/zones/{zone_id}/v{version}"
    return GenerateResponse(
        id=zone_id,
        version=version,
        mode=mode,
        zone_type=zone_type,
        rooms=rooms,
        seed=vb.seed,
        vertices=result.vertex_count,
        polygons=result.polygon_count,
        materials=result.material_count,
        glb_url=f"{base}/{zone_id}.glb",
        zone_url=f"{base}/{zone_id}.zone.json",
        map_url=f"{base}/{zone_id}.map.svg",
        eqg_url=f"{base}/{zone_id}.eqg",
        artifacts=_build_artifacts(vb.build_dir, zone_id, version),
        source=mode,
        planner=planner_name,
        plan=plan_dict,
        gates=len(vb.spec.gates),
        validated=vb.validated,
        attempts=vb.attempts,
        warnings=list(vb.warnings),
        format_passed=bool(vb.format.passed) if vb.format is not None else False,
        build_commit=BUILD_INFO["short"],
    )


# ---------------------------------------------------------------------------
# Versions of one zone (partial-rebuild Req 1, 2)
# ---------------------------------------------------------------------------

#: The stage seeds a rebuild can change, in the order ``changed`` lists them.
REBUILD_SEEDS = ("decor_seed", "rooms_seed")

VERSION_RE = re.compile(r"v([1-9][0-9]{0,5})")


class RebuildRequest(BaseModel):
    """The next version of a zone from one of its versions, changing what it names (at
    least one). ``version`` is ``2`` or ``"v2"``."""
    model_config = ConfigDict(extra="ignore")

    zone: StrictStr
    version: StrictInt | StrictStr
    decor_seed: Optional[StrictInt] = None
    rooms_seed: Optional[StrictInt] = None
    room_decor: Optional["RoomDecorChange"] = None


class RoomDecorChange(BaseModel):
    """One room keeping a decor seed of its own (the room view's Use in zone)."""
    model_config = ConfigDict(extra="forbid")

    room: StrictStr
    decor_seed: StrictInt


RebuildRequest.model_rebuild()


class VersionInfo(BaseModel):
    """A version's ``version`` block: its number, the version it was rebuilt from, the
    inputs that differ from that one, and how (``"full"``: planned again from the
    request; ``"partial"``: from the parent's saved stages)."""
    n: int
    parent: Optional[int] = None
    changed: list[str] = Field(default_factory=list)
    how: Optional[str] = None


class RebuildResponse(GenerateResponse):
    version_info: VersionInfo


#: Version numbers taken by a rebuild still running, per zone (under ``_VERSIONS_LOCK``).
_VERSIONS_LOCK = threading.Lock()
_VERSIONS_TAKEN: dict[str, set[int]] = {}


def _version_dirs(zone_dir: Path) -> dict[int, Path]:
    """A zone folder's version folders by number (``v<n>``; anything else is ignored)."""
    out: dict[int, Path] = {}
    if zone_dir.is_dir():
        for d in zone_dir.iterdir():
            m = VERSION_RE.fullmatch(d.name)
            if m and d.is_dir():
                out[int(m.group(1))] = d
    return out


def _take_version(zone: str, zone_dir: Path) -> int:
    """The zone's next version number, held for the caller until ``_release_version``: one
    past every version on disk and every number another rebuild of the zone holds, taken
    under one lock, so two rebuilds at once never share a number (or a scratch folder)."""
    with _VERSIONS_LOCK:
        taken = _VERSIONS_TAKEN.setdefault(zone, set())
        n = max(set(_version_dirs(zone_dir)) | taken, default=0) + 1
        taken.add(n)
        return n


def _release_version(zone: str, n: int) -> None:
    with _VERSIONS_LOCK:
        taken = _VERSIONS_TAKEN.get(zone, set())
        taken.discard(n)
        if not taken:
            _VERSIONS_TAKEN.pop(zone, None)


def _version_segment(version: int | str) -> str:
    """``2`` or ``"v2"`` -> ``"v2"``; anything else is a 400."""
    seg = f"v{version}" if isinstance(version, int) else version
    if not VERSION_RE.fullmatch(seg):
        raise HTTPException(400, "version must be a build version (2, or \"v2\")")
    return seg


def _zone_dir(zone: str) -> Path:
    """The zone's folder under the output root: a 400 for a name that isn't one safe
    segment or resolves outside the root, a 404 when there is no such zone."""
    from core.paths import OutsideOutputError
    if not _safe_segment(zone):
        raise HTTPException(400, "zone must be one safe name (letters, digits, _ . -)")
    try:
        zone_dir = OutputRoot(OUTPUT_DIR).path(zone)
    except OutsideOutputError:
        raise HTTPException(400, "zone must name a zone inside the output folder")
    if not zone_dir.is_dir():
        raise HTTPException(404, f"no zone {zone}")
    return zone_dir


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@app.post("/api/rebuild", response_model=RebuildResponse)
def rebuild(req: RebuildRequest):
    """The next version of ``zone`` from ``version`` (partial-rebuild Req 2), changing what the
    body names: ``decor_seed``, ``rooms_seed`` and ``room_decor: {room, decor_seed}`` (one room
    keeping a decor seed of its own; a new ``decor_seed`` clears every room's).

    A ``rooms_seed`` change is a full rebuild (``how: "full"``): the parent's ``request.json``
    sent again through Generate's path with its seed pinned. A ``decor_seed`` or ``room_decor``
    change alone is a partial one (``how: "partial"``, ``generators.rebuild``): the same
    request handling, then the build from the parent's saved spec, TER and textures; a parent
    whose saved stages are missing or no longer what this code builds takes the full path.
    Either way the new version's ``request.json`` names its seeds and room decor seeds, so a
    Generate of it builds the same zone. An unknown zone, version or room (or a version built
    before versions, with no ``request.json``) is a 404; a body naming no change, only seeds
    the parent already has, or ``room_decor`` with ``rooms_seed`` a 400; a gate failure a 503
    that writes nothing, as Generate's (a pinned decor seed is never rerolled)."""
    from generators import rebuild as partial
    zone_dir = _zone_dir(req.zone)
    parent_seg = _version_segment(req.version)
    parent_n = int(parent_seg[1:])
    for key in REBUILD_SEEDS:
        value = getattr(req, key)
        if value is not None and not (SEED_MIN <= value <= SEED_MAX):
            raise HTTPException(400, f"{key} must be between {SEED_MIN} and {SEED_MAX}")
    one = req.room_decor
    if one is not None:
        if not _safe_segment(one.room):
            raise HTTPException(400, "room_decor.room must be one safe name (letters, digits, _ . -)")
        if not (SEED_MIN <= one.decor_seed <= SEED_MAX):
            raise HTTPException(400, f"room_decor.decor_seed must be between {SEED_MIN} and {SEED_MAX}")
        if req.rooms_seed is not None:
            raise HTTPException(400, "room_decor names a room of this version: not with rooms_seed")
    if one is None and all(getattr(req, key) is None for key in REBUILD_SEEDS):
        raise HTTPException(400, "a rebuild names a change: one of "
                                 f"{', '.join(REBUILD_SEEDS)}, room_decor")

    parent_dir = _version_dirs(zone_dir).get(parent_n)
    if parent_dir is None:
        raise HTTPException(404, f"no version {req.zone}/{parent_seg}")
    saved = _read_json(parent_dir / f"{req.zone}.request.json")
    if saved is None:
        raise HTTPException(404, f"version {req.zone}/{parent_seg} has no saved request "
                                 "(built before versions)")
    if one is not None:
        spec_doc = _read_json(parent_dir / f"{req.zone}.spec.json")
        if spec_doc is None:
            raise HTTPException(404, f"version {req.zone}/{parent_seg} has no saved spec")
        if one.room not in partial.room_ids(spec_doc):
            raise HTTPException(404, f"version {req.zone}/{parent_seg} has no room {one.room!r}")

    resolved = saved.get("seeds") or {}
    changed = [key for key in REBUILD_SEEDS
               if getattr(req, key) is not None and getattr(req, key) != resolved.get(key)]
    plan = dict(saved.get("plan") or {})
    old_rooms = {str(k): v for k, v in (plan.get("room_decor_seeds") or {}).items()}
    changes = {"decor_seed": req.decor_seed if "decor_seed" in changed else None,
               "room_decor": one.model_dump() if one is not None else None}
    new_rooms = partial.room_seeds_after(old_rooms, changes) if "rooms_seed" not in changed else old_rooms
    if new_rooms != old_rooms:
        changed.append("room_decor_seeds")
    if not changed:
        raise HTTPException(400, f"version {parent_seg} already has that seed: nothing changes")

    # The request the new version is built from (and saves): the parent's, with the changed
    # seeds at the top level and the room decor seeds in its plan (and controls).
    body = dict(saved)
    for key in REBUILD_SEEDS:
        if key in changed:
            body[key] = getattr(req, key)
    if "room_decor_seeds" in changed:
        for part in ("plan", "controls"):
            if isinstance(body.get(part), dict):
                d = {k: v for k, v in body[part].items() if k != "room_decor_seeds"}
                if new_rooms:
                    d["room_decor_seeds"] = new_rooms
                body[part] = d
    try:
        gen_req = GenerateRequest.model_validate(body)
    except ValueError:
        raise HTTPException(400, f"version {req.zone}/{parent_seg} has an unreadable saved request")

    how = "full" if "rooms_seed" in changed else "partial"
    n = _take_version(req.zone, zone_dir)
    try:
        info = VersionInfo(n=n, parent=parent_n, changed=changed, how=how)
        resp = None
        if how == "partial":
            try:
                resp = _generate(gen_req, req.zone, n, saved=body, version_meta=info.model_dump(),
                                 partial=(parent_dir, changes))
            except (partial.NoSavedStages, partial.StaleStages) as exc:
                logger.warning("partial rebuild of %s/%s fell back to full: %s",
                               req.zone, parent_seg, exc)
                info = VersionInfo(n=n, parent=parent_n, changed=changed, how="full")
        if resp is None:
            resp = _generate(gen_req, req.zone, n, saved=body, version_meta=info.model_dump())
    finally:
        _release_version(req.zone, n)
    return RebuildResponse(**resp.model_dump(), version_info=info)


@app.get("/api/zones/{zone}/versions")
def list_versions(zone: str):
    """Every finished version of a zone, by number (partial-rebuild Req 1.3): ``n``,
    ``parent``, ``changed``, ``how`` (from its sidecar's ``version`` block; v1 has none),
    its ``seeds``, ``created`` and ``took_ms`` (from its ``request.json``; ``created``
    falls back to the sidecar's time) and the URLs that open it."""
    zone_dir = _zone_dir(zone)
    versions = []
    for n, vdir in sorted(_version_dirs(zone_dir).items()):
        sidecar_path = vdir / f"{zone}.zone.json"
        sidecar = _read_json(sidecar_path)
        if sidecar is None:
            continue                       # not a finished build
        block = sidecar.get("version") or {}
        saved = _read_json(vdir / f"{zone}.request.json") or {}
        created = saved.get("created")
        if created is None:
            created = datetime.fromtimestamp(sidecar_path.stat().st_mtime,
                                             tz=timezone.utc).isoformat(timespec="seconds")
        base = f"/api/zones/{zone}/v{n}"
        versions.append({
            "n": n, "parent": block.get("parent"), "changed": list(block.get("changed", [])),
            "how": block.get("how"), "seeds": sidecar.get("seeds"),
            "created": created, "took_ms": saved.get("took_ms"),
            "glb_url": f"{base}/{zone}.glb", "zone_url": f"{base}/{zone}.zone.json",
            "map_url": f"{base}/{zone}.map.svg", "eqg_url": f"{base}/{zone}.eqg",
        })
    if not versions:
        raise HTTPException(404, f"zone {zone} has no finished version")
    return {"zone": zone, "versions": versions}


# ---------------------------------------------------------------------------
# The room view (decor-rules Req 4): re-decorate one room of a build
# ---------------------------------------------------------------------------

class RoomDecorRequest(BaseModel):
    """One room of an accepted build to re-decorate. ``decor_seed``, ``control`` and
    ``decor_layers`` default to what the build's Decor ran with (its sidecar). ``decor_layers``
    names extra layers on top of the dungeon theme's and race's, as ``/api/generate``'s does
    (``[]``: the theme's alone)."""
    model_config = ConfigDict(extra="ignore")

    zone: StrictStr
    version: StrictInt | StrictStr = 1
    room: StrictStr
    decor_seed: Optional[StrictInt] = None
    control: Optional[StrictStr] = None
    decor_layers: Optional[list[StrictStr]] = None


#: The room view's per-build inputs (RoomContexts, sidecar defaults, the built wall mesh),
#: by (zone, version): (rooms file mtime, ``room_view.Build``). The rules are never kept.
_ROOM_BUILDS: dict[tuple[str, str], tuple[int, Any]] = {}
ROOM_BUILDS_KEPT = 4
#: Room GLBs kept per room in a build folder (older rerolls are removed).
ROOM_GLBS_KEPT = 8


def _room_eq_path() -> Optional[Path]:
    """The install the room view reads models from: the build's (``EQ_PATH``)."""
    from generators.decor.stock import eq_path_from_env
    return eq_path_from_env()


def _room_build(zone: str, version: str, build_dir: Path):
    """The build's room view inputs, read once per (zone, version) while its rooms file is
    unchanged."""
    from generators.decor.room_view import _file, load_build
    rooms = _file(build_dir, zone, ".rooms.json")
    if not rooms.is_file():
        raise HTTPException(404, f"build {zone}/{version} has no RoomContexts "
                                 "(built with Decor none, or without the install)")
    mtime = rooms.stat().st_mtime_ns
    key = (zone, version)
    hit = _ROOM_BUILDS.get(key)
    if hit is None or hit[0] != mtime:
        build = load_build(build_dir, zone)
        _ROOM_BUILDS.pop(key, None)
        while len(_ROOM_BUILDS) >= ROOM_BUILDS_KEPT:
            _ROOM_BUILDS.pop(next(iter(_ROOM_BUILDS)))
        _ROOM_BUILDS[key] = hit = (mtime, build)
    return hit[1]


@app.post("/api/room_decor")
def room_decor(req: RoomDecorRequest):
    """Re-decorate one room of an accepted build (decor-rules Req 4) from the build's saved
    RoomContexts, with the rule files read fresh, and answer its report (the Props with their
    recipe lines, the POIs with their Dressing, the drops with their reasons) with a
    ``glb_url``: the room alone, written into the build folder and served by the build-file
    route. Every id is a safe path segment inside the output root (400 otherwise); an unknown
    build or room is a 404; a rule file that fails its check is a 400 listing the failures."""
    from ai import schema
    from generators.decor.room_view import NoRoom, decorate_room
    from generators.decor.rules import CONTROLS, layers_for
    from generators.topology.ruleset import RuleSetError
    from core.paths import OutsideOutputError

    zone = req.zone
    version = f"v{req.version}" if isinstance(req.version, int) else req.version
    if not re.fullmatch(r"v[0-9]{1,6}", version):
        raise HTTPException(400, "version must be a build version (1, or \"v1\")")
    if not all(_safe_segment(s) for s in (zone, version, req.room)):
        raise HTTPException(400, "zone and room must each be one safe name (letters, digits, _ . -)")
    if req.decor_seed is not None and not (SEED_MIN <= req.decor_seed <= SEED_MAX):
        raise HTTPException(400, f"decor_seed must be between {SEED_MIN} and {SEED_MAX}")
    if req.control is not None and req.control not in CONTROLS:
        raise HTTPException(400, f"control must be one of {', '.join(CONTROLS)}")
    rules_dir = schema.RULES_DECOR_DIR
    extra: Optional[tuple] = None
    if req.decor_layers is not None:
        try:
            extra = schema.decor_layers(req.decor_layers, rules_dir)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    root = OutputRoot(OUTPUT_DIR)
    try:
        build_dir = root.path(zone, version)
    except OutsideOutputError:
        raise HTTPException(400, "zone and version must name a build inside the output folder")
    if not build_dir.is_dir():
        raise HTTPException(404, f"no build {zone}/{version}")
    build = _room_build(zone, version, build_dir)

    control = req.control or build.control
    try:
        layers = build.layers if extra is None else layers_for(build.theme, build.race, extra, rules_dir)
        # The zone's decor seed draws the room's bare decision, as the build drew it; a
        # ``decor_seed`` here is the room's own (a reroll), and "As built" (none) takes the
        # room's own seed from the build when it has one (partial-rebuild Req 3.2, 3.4).
        glb, report = decorate_room(build.contexts, req.room, seed=build.seed, control=control,
                                    layers=layers, eq_path=_room_eq_path(), mesh=build.mesh,
                                    rules_dir=rules_dir, room_seed=req.decor_seed,
                                    room_seeds=build.room_seeds)
    except NoRoom:
        raise HTTPException(404, f"build {zone}/{version} has no room {req.room!r}; it has "
                                 + ", ".join(c.id for c in build.contexts))
    except RuleSetError as exc:
        raise HTTPException(400, {"message": "the decor rules fail their check",
                                  "errors": [str(e) for e in exc.errors]})

    fname = f"room_{req.room}_{hashlib.sha1(glb).hexdigest()[:10]}.glb"
    target = root.write_bytes(f"{zone}/{version}/{fname}", glb)
    olds = sorted((p for p in build_dir.glob(f"room_{req.room}_*.glb") if p.name != target.name),
                  key=lambda p: p.stat().st_mtime_ns)
    for old in olds[:max(0, len(olds) - (ROOM_GLBS_KEPT - 1))]:
        root.path(zone, version, old.name).unlink(missing_ok=True)
    return {"zone": zone, "version": version, **report,
            "glb_url": f"/api/zones/{zone}/{version}/{fname}"}


def _eqmap_layer(stem: str, name: str) -> Optional[int]:
    """The layer of an EQ map file stem: ``<name>`` is 0, ``<name>_N`` is N."""
    if stem == name:
        return 0
    m = re.fullmatch(re.escape(name) + r"_([1-9])", stem)
    return int(m.group(1)) if m else None


def _build_artifacts(build_dir: Optional[Path], name: str,
                     version: int) -> list[ArtifactRef]:
    """The files actually present in an accepted build's directory, in panel
    order: map SVG, EQ map layers (ascending), archive, preview, sidecar."""
    if build_dir is None:
        return []
    base = f"/api/zones/{name}/v{version}"
    refs: list[ArtifactRef] = []

    def add(kind: str, rel: str, layer: Optional[int] = None) -> None:
        if (build_dir / rel).is_file():
            refs.append(ArtifactRef(kind=kind, filename=rel,
                                    url=f"{base}/{rel}", layer=layer))

    add("map_svg", f"{name}.map.svg")
    maps_dir = build_dir / MAPS_SUBDIR
    if maps_dir.is_dir():
        layers = sorted((layer, p.name) for p in maps_dir.glob("*.txt")
                        if (layer := _eqmap_layer(p.stem, name)) is not None)
        for layer, fname in layers:
            add("eqmap", f"{MAPS_SUBDIR}/{fname}", layer)
    add("eqg", f"{name}.eqg")
    add("glb", f"{name}.glb")
    add("sidecar", f"{name}.zone.json")
    return refs


@app.api_route("/api/zones/{zone_id}/{version}/{filename}", methods=["GET", "HEAD"])
@app.api_route("/api/zones/{zone_id}/{version}/{subdir}/{filename}",
               methods=["GET", "HEAD"])
def get_zone_file(zone_id: str, version: str, filename: str,
                  subdir: Optional[str] = None):
    """Serve one artifact from a per-build directory (GET and HEAD).

    An accepted build lives at ``OUTPUT_DIR/<zone_id>/v<version>/`` with its EQ
    map files under ``maps/``; ``maps`` is the only subfolder served. Every URL
    segment must be a single safe component (``SEGMENT_RE``, no ``..``), the
    extension must be in that folder's allow-list, and the resolved path must
    lie inside the build directory under ``OUTPUT_DIR``. Any failed check is a
    400 with no body, decided before any file access; a well-formed request for
    a file that is not present is a 404, also bodiless so HEAD and GET agree. ``FileResponse`` serves the bytes as
    stored and answers HEAD with the same headers and no body.
    """
    parts = (zone_id, version) + ((subdir,) if subdir is not None else ()) + (filename,)
    if not all(_safe_segment(seg) for seg in parts):
        return Response(status_code=400)
    if subdir is not None and subdir != MAPS_SUBDIR:
        return Response(status_code=400)

    allowed = MAPS_FILE_EXTS if subdir is not None else BUILD_FILE_EXTS
    if not filename.lower().endswith(allowed):
        return Response(status_code=400)

    # Belt-and-braces: resolve the candidate and confirm it is still inside the
    # build directory within OUTPUT_DIR. The segment checks already block
    # traversal, but re-checking after resolution means a path can never escape
    # even if those checks are later loosened.
    build_dir = (OUTPUT_DIR / zone_id / version).resolve()
    candidate = (build_dir / Path(*parts[2:])).resolve()
    if not OutputRoot(OUTPUT_DIR).contains(candidate) or build_dir not in candidate.parents:
        return Response(status_code=400)

    if not candidate.is_file():
        return Response(status_code=404)

    return FileResponse(str(candidate),
                        media_type=_MEDIA_BY_EXT.get(_file_extension(filename),
                                                     "application/octet-stream"))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/version")
def version():
    """The code this process loaded at startup vs. the code on disk now.

    ``stale`` is True when HEAD moved or any server-side .py file changed
    (mtime/size) since startup — i.e. the running server needs a restart for
    its output to match the source tree.
    """
    current_commit = _current_commit()
    current_fp = _source_fingerprint()
    return {
        **BUILD_INFO,
        "current_commit": current_commit,
        "current_fingerprint": current_fp,
        "stale": (current_commit != BUILD_INFO["commit"]
                  or current_fp != BUILD_INFO["source_fingerprint"]),
    }


# ---------------------------------------------------------------------------
# Serve the built front-end (if present). During development the Vite dev
# server runs separately on :5173; in production `vite build` fills web/dist.
# ---------------------------------------------------------------------------

if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host=HOST, port=PORT, reload=False)
