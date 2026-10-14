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

import random
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
from generators.builder import ZoneBuilder
from analyzer.style_builder import REFERENCE_ZONES

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).parent.parent
OUTPUT_DIR  = ROOT / "output" / "web"
WEB_DIST    = ROOT / "web" / "dist"      # built front-end (Vite build)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VALID_THEMES = ["dungeon", "outdoor", "cave", "city"]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="eq_s3d zone generator", version="0.3.0")

# Allow the Vite dev server (localhost:5173) to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    theme: str = Field(default="dungeon", description="Zone theme")
    rooms: int = Field(default=5, ge=1, le=30, description="Number of rooms")
    elevation: bool = Field(default=True, description="Allow multi-level layout")
    seed: Optional[int] = Field(default=None, description="Pin a seed (omit for random)")
    # Prompt field reserved for Phase 3 — accepted but not yet used
    prompt: Optional[str] = None


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
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"Unknown theme: {req.theme}")

    # Fresh random seed every call unless the caller pins one.
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    # Unique zone id so repeated generations don't collide on disk.
    zone_id = f"gen_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    gen = LayoutGenerator(theme=req.theme, seed=seed)
    spec = gen.generate(zone_id, room_count=req.rooms, elevation=req.elevation)

    result = ZoneBuilder(spec).build(output_dir=OUTPUT_DIR, write_glb=True)

    if result.glb_path is None:
        raise HTTPException(500, "GLB export failed (is trimesh installed?)")

    return GenerateResponse(
        id=zone_id,
        theme=req.theme,
        rooms=req.rooms,
        seed=seed,
        vertices=result.vertex_count,
        polygons=result.polygon_count,
        materials=result.material_count,
        glb_url=f"/api/zones/{zone_id}.glb",
        zone_url=f"/api/zones/{zone_id}.zone.json",
    )


@app.get("/api/zones/{filename}")
def get_zone_file(filename: str):
    # Guard against path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")

    media = "model/gltf-binary" if filename.endswith(".glb") else "application/json"
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
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=False)
