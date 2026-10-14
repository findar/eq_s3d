"""
viewer/serve.py
---------------
Minimal Flask server that serves the Three.js zone preview viewer.

Usage::

    python -m viewer.serve output/myzone.glb
    # Opens http://localhost:5173 automatically

The viewer auto-reloads when the GLB file changes (polls every 2 seconds).
"""

from __future__ import annotations

import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

from flask import Flask, send_file, send_from_directory, jsonify

app = Flask(__name__, static_folder=str(Path(__file__).parent))

_GLB_PATH: Path = Path("output/preview.glb")
_GLB_MTIME: float = 0.0
_PORT = 5173


@app.route("/")
def index():
    return send_from_directory(str(Path(__file__).parent), "index.html")


@app.route("/zone.glb")
def zone_glb():
    if not _GLB_PATH.exists():
        return "GLB not found", 404
    return send_file(str(_GLB_PATH), mimetype="model/gltf-binary")


@app.route("/status")
def status():
    """Polled by the viewer to detect when a new GLB is available."""
    mtime = _GLB_PATH.stat().st_mtime if _GLB_PATH.exists() else 0
    return jsonify({"mtime": mtime})


def _open_browser():
    time.sleep(1.0)
    webbrowser.open(f"http://localhost:{_PORT}")


def serve(glb_path: str | Path, port: int = _PORT) -> None:
    global _GLB_PATH
    _GLB_PATH = Path(glb_path)
    print(f"[viewer] Serving {_GLB_PATH.name} at http://localhost:{port}")
    t = threading.Thread(target=_open_browser, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    glb = sys.argv[1] if len(sys.argv) > 1 else "output/preview.glb"
    serve(glb)
