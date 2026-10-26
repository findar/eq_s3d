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
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from generators.pipeline import generate_validated, GenerationFailed
from generators.zone_types import (
    DEFINED_ZONE_TYPES, DEFAULT_ZONE_TYPE, canonical_zone_type,
    ENABLED_ZONE_TYPES, is_enabled, zone_type_listing,
)
from analyzer.style_builder import REFERENCE_ZONES
from ai.planner import make_plan, get_planner
from ai.expand import plan_to_spec
from ai.schema import ZonePlan

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).parent.parent
OUTPUT_DIR  = ROOT / "output" / "web"
WEB_DIST    = ROOT / "web" / "dist"      # built front-end (Vite build)
FAILURE_LOG = ROOT / "output" / "validation_failures.jsonl"  # triage feed
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# The available zone types come from the single source of truth
# (generators/zone_types.py); the server no longer keeps its own list.
VALID_ZONE_TYPES = list(DEFINED_ZONE_TYPES)

# ---------------------------------------------------------------------------
# Per-build file serving (task 15.5)
# ---------------------------------------------------------------------------
#
# The pipeline (task 15.4) moves an accepted build's files into
# output/web/<zone_id>/v<version>/<zone_id>.*. The route that serves them
# (`/api/zones/{zone_id}/{version}/{filename}`) is deliberately strict: each URL
# segment must match SEGMENT_RE (no separators, no `..`), the file extension
# must be in BUILD_FILE_EXTS, and the resolved path must still lie inside
# OUTPUT_DIR after resolution — so no crafted segment can read outside the
# output tree. The detailed traversal example tests are task 15.9; the guards
# are implemented correctly here.

# A single path segment: letters, digits, underscore, dot and hyphen only, and
# never exactly "..". Rejects `/`, `\`, drive letters and parent-dir hops.
SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# The artifact extensions a build directory is allowed to serve. Anything else
# (e.g. a stray ``.py`` or ``.jsonl``) is refused before any file access.
BUILD_FILE_EXTS = {".glb", ".eqg", ".svg", ".json"}

# Extension -> media type for the FileResponse.
_MEDIA_BY_EXT = {
    ".glb": "model/gltf-binary",
    ".eqg": "application/octet-stream",
    ".svg": "image/svg+xml",
    ".json": "application/json",
}


def _file_extension(filename: str) -> str:
    """The build-file extension for ``filename``.

    Multi-dot names like ``gen_123.zone.json`` / ``gen_123.map.svg`` keep their
    final extension (``.json`` / ``.svg``), which is what the allow-list checks.
    """
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""

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

app = FastAPI(title="eq_s3d zone generator", version="0.3.0")


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
    if not request.url.path.startswith("/api/generate"):
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
        if field in ("seed", "rooms", "room_count", "locks"):
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
    ``bool`` (an ``int`` subclass in Python) and any non-int kind (float, string,
    list, null) raise an :class:`HTTPException` 400 that names the field, so a
    malformed ``controls.room_count`` / ``controls.locks`` is a 400 — never a
    silent coercion and never a raw 422 (Req 2.5).
    """
    if key not in d or d[key] is None:
        return
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise HTTPException(400, f"{key} must be an integer")


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
                    "verticality, locks, …",
    )
    # ``seed`` is StrictInt so a float/bool/string is a validation error (-> 400
    # via the RequestValidationError handler), never a silent coercion.
    seed: Optional[StrictInt] = Field(
        default=None, description="Pin a seed (omit for random)")

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
    zone_id = f"gen_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # --- Mode + seed resolution: every 400 here happens BEFORE any build/write.
    mode = _resolve_mode(req)

    # A pinned seed must be in the 32-bit non-negative Pinned_Seed domain. (Its
    # integer *kind* is already guaranteed by StrictInt via the 400 handler.)
    if req.seed is not None and not (SEED_MIN <= req.seed <= SEED_MAX):
        raise HTTPException(
            400, f"seed must be between {SEED_MIN} and {SEED_MAX}")

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
        planner_name = get_planner().name
        plan = make_plan(prompt, name=zone_id)
        # Guard the Build_Name: no planner output chooses the directory/file stem.
        plan.name = zone_id

        # A prompt-planned DISABLED zone type is not refused — it is substituted
        # to dungeon so the prompt still yields a zone, with a
        # ``zone_type_substituted:<planned>->dungeon`` warning for the UI and the
        # planned zone type recorded in the Sidecar (Req 3.3).
        if not is_enabled(plan.zone_type):
            planned_zone_type = plan.zone_type
            plan.zone_type = DEFAULT_ZONE_TYPE
            warnings.append(
                f"zone_type_substituted:{planned_zone_type}->{DEFAULT_ZONE_TYPE}"
            )
        else:
            # The planned type is enabled: canonicalise it so a legacy value
            # (e.g. ``outdoor``) builds as its current name, mirroring the
            # controls path. The built/returned zone_type is always a canonical
            # member of the Enabled set.
            plan.zone_type = canonical_zone_type(plan.zone_type)

        plan_dict = plan.to_dict()
        zone_type = plan.zone_type
        rooms = plan.room_count

        def factory(s: int):
            return plan_to_spec(plan, seed=s)
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

        # Proven equal to the legacy LayoutGenerator path by the 17.4 golden test.
        plan = ZonePlan.from_controls(c, warnings)
        plan.name = zone_id
        plan_dict = plan.to_dict()
        zone_type = plan.zone_type
        rooms = plan.room_count

        def factory(s: int):
            return plan_to_spec(plan, seed=s)

    # Build + traversability gate. On gated themes a failing dungeon seed is
    # never returned: the pipeline retries on fresh seeds (bounded by attempts +
    # timeout) and returns the first passing zone, or raises GenerationFailed.
    try:
        vb = generate_validated(
            factory,
            zone_type=zone_type,
            zone_id=zone_id,
            seed=req.seed,
            output_dir=OUTPUT_DIR,
            write_glb=True,
            failure_log=FAILURE_LOG,
            warnings=warnings,
            planned_zone_type=planned_zone_type,
            mode=mode,
        )
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
    return GenerateResponse(
        id=zone_id,
        version=1,
        mode=mode,
        zone_type=zone_type,
        rooms=rooms,
        seed=vb.seed,
        vertices=result.vertex_count,
        polygons=result.polygon_count,
        materials=result.material_count,
        glb_url=f"/api/zones/{zone_id}/v1/{zone_id}.glb",
        zone_url=f"/api/zones/{zone_id}/v1/{zone_id}.zone.json",
        map_url=f"/api/zones/{zone_id}/v1/{zone_id}.map.svg",
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


@app.get("/api/zones/{zone_id}/{version}/{filename}")
def get_zone_file(zone_id: str, version: str, filename: str):
    """Serve one artifact from a per-build directory.

    An accepted build lives at ``OUTPUT_DIR/<zone_id>/v<version>/<zone_id>.*``
    (task 15.4). Every URL segment must be a single safe path component
    (``SEGMENT_RE``, never ``..``), the extension must be in the allow-list, and
    the path, once resolved, must still lie inside ``OUTPUT_DIR`` — so no
    crafted segment can read outside the output tree. A well-formed request for
    a file that is not present is a 404; a malformed segment or a disallowed
    extension is a 400 (both raised before any file access).
    """
    # Each segment must be a single safe component — no separators, no parent-dir
    # hop. (A `/` or `\` in a segment can't even reach here as one path param,
    # but an explicit check keeps the guard self-evident and covers `..`.)
    for seg in (zone_id, version, filename):
        if seg == ".." or not SEGMENT_RE.match(seg):
            raise HTTPException(400, "Invalid path segment")

    # Only build artifacts are served; refuse any other extension outright.
    ext = _file_extension(filename)
    if ext not in BUILD_FILE_EXTS:
        raise HTTPException(400, f"Disallowed file type: {ext or '(none)'}")

    # Belt-and-braces: resolve the candidate and confirm it is still inside
    # OUTPUT_DIR. The segment regex already blocks traversal, but resolving and
    # re-checking means a path can never escape the output root even if the
    # regex is later loosened.
    base = OUTPUT_DIR.resolve()
    candidate = (OUTPUT_DIR / zone_id / version / filename).resolve()
    if candidate != base and base not in candidate.parents:
        raise HTTPException(400, "Path escapes the output directory")

    if not candidate.is_file():
        raise HTTPException(404, "Not found")

    return FileResponse(str(candidate),
                        media_type=_MEDIA_BY_EXT.get(ext, "application/octet-stream"))


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
