"""
tests/test_server.py
---------------------
Example / smoke tests for the loopback-bound, CORS-restricted FastAPI server
(``server/app.py``). These cover the M0 server acceptance criteria that are
best checked by concrete examples; the foreign-origin *property* test
(Property 18, Req 9.3) lives in task 7.3 and is added separately.

What each test maps to (this spec's design "Server" test list):
  - 9.1: ``python -m server.app`` binds HOST/PORT, with no real socket bind.
  - 9.2: Access-Control-Allow-Origin is echoed byte-identically for each of the
         four WEB_APP_ORIGINS.
  - 9.4: no response ever carries a wildcard ``*`` ACAO (the shared
         ``assert_no_wildcard`` helper, applied to every response below).
  - 9.5: a real generate + file fetch round-trip from an allowed origin, into a
         tmp output dir, carries ACAO on every response and is validated.
  - 9.6: an allowed-origin preflight returns 200 with a matching ACAO and the
         expected Allow-Methods / Allow-Headers.
  - 9.7: a request with no Origin gets no ``Access-Control-Allow-*`` header.

The server reads ``OUTPUT_DIR`` / ``FAILURE_LOG`` as module globals at request
time, so monkeypatching ``server.app.OUTPUT_DIR`` / ``server.app.FAILURE_LOG``
to a ``tmp_path`` keeps generated artifacts out of the worktree.
"""

from __future__ import annotations

import runpy

import pytest
from fastapi.testclient import TestClient

import server.app as app_mod
from server.app import WEB_APP_ORIGINS, HOST, PORT


# A dungeon seed that passes the traversability gate for a pinned 3-room build
# (verified across seeds 1..1955208177; a pinned failure would 503, so this must
# be a seed that validates). Kept small and explicit for readability.
PINNED_SEED = 42
ROOMS = 3


# ---------------------------------------------------------------------------
# Shared guard (Req 9.4): no response may hand out a wildcard CORS grant.
# ---------------------------------------------------------------------------

def assert_no_wildcard(resp):
    """No ``Access-Control-Allow-Origin`` header may be, or contain, ``*``.

    Req 9.4 forbids a wildcard grant on any response. ``httpx`` header lookup is
    case-insensitive; a missing header is fine (that's the no-grant case).
    Returns ``resp`` so callers can route every response through it inline.
    """
    acao = resp.headers.get("access-control-allow-origin")
    if acao is not None:
        assert "*" not in acao, f"wildcard ACAO leaked: {acao!r}"
    return resp


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient whose server writes artifacts into an isolated tmp dir."""
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


# ---------------------------------------------------------------------------
# 9.1 — __main__ binds HOST/PORT with no real socket bind
# ---------------------------------------------------------------------------

def test_main_binds_host_and_port(monkeypatch):
    """Running the module as ``__main__`` calls ``uvicorn.run`` with the
    loopback HOST and PORT — captured, never actually bound (Req 9.1)."""
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        # Return without binding anything.

    import uvicorn
    monkeypatch.setattr(uvicorn, "run", fake_run)

    runpy.run_module("server.app", run_name="__main__")

    assert captured, "uvicorn.run was never called by the __main__ path"
    kw = captured["kwargs"]
    assert kw["host"] == HOST == "127.0.0.1"
    assert kw["port"] == PORT == 8000


# ---------------------------------------------------------------------------
# 9.2 — ACAO echoed byte-identically for each allowed origin
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("origin", list(WEB_APP_ORIGINS))
def test_health_echoes_origin(client, origin):
    """GET /api/health from each allowed origin echoes that exact Origin back
    in Access-Control-Allow-Origin (byte-identical, never ``*``) — Req 9.2."""
    resp = assert_no_wildcard(
        client.get("/api/health", headers={"Origin": origin})
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


# ---------------------------------------------------------------------------
# 9.5 — generate + file fetch round-trip from an allowed origin
# ---------------------------------------------------------------------------

def test_generate_and_fetch_files(client):
    """A pinned 3-room dungeon generate from an allowed origin returns a
    validated build, and the returned glb_url / zone_url each fetch 200 with the
    Origin echoed on every response (Req 9.5)."""
    origin = "http://localhost:5173"
    headers = {"Origin": origin}

    resp = assert_no_wildcard(
        client.post(
            "/api/generate",
            json={"theme": "dungeon", "rooms": ROOMS, "seed": PINNED_SEED},
            headers=headers,
        )
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("access-control-allow-origin") == origin

    body = resp.json()
    assert body["validated"] is True
    assert body["rooms"] == ROOMS

    for url_field in ("glb_url", "zone_url"):
        url = body[url_field]
        file_resp = assert_no_wildcard(client.get(url, headers=headers))
        assert file_resp.status_code == 200, f"{url_field} ({url}) -> {file_resp.status_code}"
        assert file_resp.headers.get("access-control-allow-origin") == origin


# ---------------------------------------------------------------------------
# 9.6 — allowed-origin preflight carries a matching grant
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("origin", list(WEB_APP_ORIGINS))
def test_preflight_from_allowed_origin(client, origin):
    """An OPTIONS preflight for POST + content-type from an allowed origin
    returns 200 with ACAO echoed, Allow-Methods including POST, and
    Allow-Headers including content-type (Req 9.6)."""
    resp = assert_no_wildcard(
        client.options(
            "/api/generate",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin

    allow_methods = resp.headers.get("access-control-allow-methods", "")
    methods = {m.strip().upper() for m in allow_methods.split(",") if m.strip()}
    assert "POST" in methods, f"Allow-Methods missing POST: {allow_methods!r}"

    allow_headers = resp.headers.get("access-control-allow-headers", "")
    headers_lower = {h.strip().lower() for h in allow_headers.split(",") if h.strip()}
    assert "content-type" in headers_lower, (
        f"Allow-Headers missing content-type: {allow_headers!r}"
    )


# ---------------------------------------------------------------------------
# 9.7 — no Origin -> no CORS grant
# ---------------------------------------------------------------------------

def test_no_origin_no_cors_headers(client):
    """A request with no Origin header succeeds but carries no
    Access-Control-Allow-* header (Req 9.7)."""
    resp = assert_no_wildcard(client.get("/api/health"))
    assert resp.status_code == 200
    for name in resp.headers:
        assert not name.lower().startswith("access-control-allow-"), (
            f"unexpected CORS header on an origin-less request: {name}"
        )


# ---------------------------------------------------------------------------
# M0 6.7 — controls path rejects the removed "cave" theme
# ---------------------------------------------------------------------------

def test_controls_cave_theme_rejected(client):
    """A control-driven generate with theme="cave" is a 400 whose detail names
    all three valid themes, and nothing is written to OUTPUT_DIR (M0 Req 6.7)."""
    resp = assert_no_wildcard(
        client.post("/api/generate", json={"theme": "cave", "rooms": ROOMS})
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    for theme in ("dungeon", "outdoor", "city"):
        assert theme in detail, f"detail does not name {theme!r}: {detail!r}"
    # The 400 is raised before the factory runs, so no artifacts are produced.
    assert list(app_mod.OUTPUT_DIR.iterdir()) == []
