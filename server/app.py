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

import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from generators.layout import LayoutGenerator
from generators.pipeline import generate_validated, GenerationFailed
from analyzer.style_builder import REFERENCE_ZONES
from ai.planner import make_plan, get_planner
from ai.expand import plan_to_spec

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).parent.parent
OUTPUT_DIR  = ROOT / "output" / "web"
WEB_DIST    = ROOT / "web" / "dist"      # built front-end (Vite build)
FAILURE_LOG = ROOT / "output" / "validation_failures.jsonl"  # triage feed
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VALID_THEMES = ["dungeon", "outdoor", "cave", "city"]

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


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    # If `prompt` is set, the planner derives theme/rooms/etc. from it and the
    # explicit fields below are ignored. Otherwise the explicit fields drive it.
    prompt: Optional[str] = Field(default=None, description="Natural-language prompt")
    theme: str = Field(default="dungeon", description="Zone theme (ignored if prompt set)")
    rooms: int = Field(default=5, ge=1, le=30, description="Number of rooms")
    elevation: bool = Field(default=True, description="Allow multi-level layout")
    seed: Optional[int] = Field(default=None, description="Pin a seed (omit for random)")


class GenerateResponse(BaseModel):
    id: str
    theme: str
    rooms: int
    seed: int
    vertices: int
    polygons: int
    materials: int
    glb_url: str
    zone_url: str
    map_url: str
    # What drove the generation (so the UI can show inferred choices)
    source: str                      # "prompt" | "controls"
    planner: Optional[str] = None    # "rule" | "llm" when a prompt was used
    plan: Optional[dict] = None      # the ZonePlan the planner produced
    gates: int = 0                   # number of lock-and-key gates (keyed dungeon)
    # Traversability gate provenance (see generators/pipeline.py).
    validated: bool = False          # did the traversability gate run AND pass?
    attempts: int = 1                # builds it took (fresh-seed retries on failure)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/themes")
def list_themes():
    """Available themes and the reference zones each profile was built from."""
    return {
        "themes": VALID_THEMES,
        "reference_zones": {k: v for k, v in REFERENCE_ZONES.items()},
    }


@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    zone_id = f"gen_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    prompt = (req.prompt or "").strip()
    plan_dict = None
    planner_name = None

    if prompt:
        # Prompt-driven: the planner derives the full spec. The plan is
        # seed-independent (it comes from the prompt), so build it once and let
        # the pipeline re-run spec expansion per fresh-seed retry.
        source = "prompt"
        planner_name = get_planner().name
        plan = make_plan(prompt, name=zone_id)
        plan_dict = plan.to_dict()
        theme = plan.theme
        rooms = plan.room_count

        def factory(s: int):
            return plan_to_spec(plan, seed=s)
    else:
        # Control-driven: explicit theme/rooms/elevation.
        source = "controls"
        if req.theme not in VALID_THEMES:
            raise HTTPException(400, f"Unknown theme: {req.theme}")
        theme = req.theme
        rooms = req.rooms

        def factory(s: int):
            return LayoutGenerator(theme=theme, seed=s).generate(
                zone_id, room_count=rooms, elevation=req.elevation,
            )

    # Build + traversability gate. On gated themes a failing dungeon seed is
    # never returned: the pipeline retries on fresh seeds (bounded by attempts +
    # timeout) and returns the first passing zone, or raises GenerationFailed.
    try:
        vb = generate_validated(
            factory,
            theme=theme,
            zone_id=zone_id,
            seed=req.seed,
            output_dir=OUTPUT_DIR,
            write_glb=True,
            failure_log=FAILURE_LOG,
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

    return GenerateResponse(
        id=zone_id,
        theme=theme,
        rooms=rooms,
        seed=vb.seed,
        vertices=result.vertex_count,
        polygons=result.polygon_count,
        materials=result.material_count,
        glb_url=f"/api/zones/{zone_id}.glb",
        zone_url=f"/api/zones/{zone_id}.zone.json",
        map_url=f"/api/zones/{zone_id}.map.svg",
        source=source,
        planner=planner_name,
        plan=plan_dict,
        gates=len(vb.spec.gates),
        validated=vb.validated,
        attempts=vb.attempts,
    )


@app.get("/api/zones/{filename}")
def get_zone_file(filename: str):
    # Guard against path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")

    if filename.endswith(".glb"):
        media = "model/gltf-binary"
    elif filename.endswith(".svg"):
        media = "image/svg+xml"
    else:
        media = "application/json"
    return FileResponse(str(path), media_type=media)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Serve the built front-end (if present). During development the Vite dev
# server runs separately on :5173; in production `vite build` fills web/dist.
# ---------------------------------------------------------------------------

if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host=HOST, port=PORT, reload=False)
