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
        client.post("/api/generate", json={"zone_type": "cave", "rooms": ROOMS})
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    for zt in ("dungeon", "wilderness", "city"):
        assert zt in detail, f"detail does not name {zt!r}: {detail!r}"
    # The 400 is raised before the factory runs, so no artifacts are produced.
    assert list(app_mod.OUTPUT_DIR.iterdir()) == []

# ---------------------------------------------------------------------------
# Property 18 (Req 9.3, 9.4) — foreign origins get no CORS grant
# ---------------------------------------------------------------------------
#
# A module-scoped TestClient is used here on purpose: @given tests must not take
# function-scoped fixtures (tmp_path/monkeypatch), which would trip Hypothesis'
# function_scoped_fixture health check by being reset only once per test, not
# per example. These foreign-origin requests never write artifacts anyway:
#   - GET /api/health is a trivial handler that touches no output dir;
#   - the POST deliberately carries theme="cave", which the controls path
#     rejects with a 400 *before* any factory/build runs (M0 6.7), so no zone is
#     generated regardless of the drawn origin;
#   - the preflight (OPTIONS) returns before any handler body.
# So no OUTPUT_DIR monkeypatch is needed to keep the worktree clean.

from hypothesis import given, settings  # noqa: E402

from tests.pbt_helpers import scaled  # noqa: E402
from tests.strategies import origins_outside  # noqa: E402

# Built once at import time (no per-example fixture): foreign-origin requests
# are rejected at the CORS layer / fail fast, so a shared client is safe.
_FOREIGN_CLIENT = TestClient(app_mod.app)


def _assert_no_cors_grant(resp, origin):
    """No ``Access-Control-Allow-*`` header of any kind, and no wildcard ACAO.

    This is the core of Req 9.3/9.4 for a disallowed origin: the response must
    neither echo the foreign origin nor hand out ``*`` — it must carry no
    ``Access-Control-Allow-*`` header at all.
    """
    assert_no_wildcard(resp)  # reuse the 7.2 helper: forbids ``*`` ACAO
    leaked = [n for n in resp.headers
              if n.lower().startswith("access-control-allow-")]
    assert not leaked, (
        f"foreign origin {origin!r} received CORS grant header(s): {leaked}"
    )


@settings(max_examples=scaled(100))
@given(origin=origins_outside)
def test_foreign_origins_get_no_cors(origin):
    """Feature: zone-generator-m0-hygiene, Property 18 (umbrella P-CORS):
    Foreign origins get no CORS grant.

    For ANY Origin outside WEB_APP_ORIGINS (random printable strings plus the
    scheme / host-case / port / trailing-slash near-misses, ``null`` and the
    IPv6 loopback), a simple GET, a simple POST and a CORS preflight (OPTIONS)
    each come back with NO ``Access-Control-Allow-*`` header — in particular no
    ``Access-Control-Allow-Origin: *``.

    Validates: M0 Req 9.3, 9.4
    """
    # (a) a simple GET
    get_resp = _FOREIGN_CLIENT.get(
        "/api/health", headers={"Origin": origin}
    )
    _assert_no_cors_grant(get_resp, origin)

    # (b) a CORS preflight for POST + content-type (foreign preflight is
    # stripped of its grant by LocalCORSMiddleware before any handler runs)
    pre_resp = _FOREIGN_CLIENT.options(
        "/api/generate",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    _assert_no_cors_grant(pre_resp, origin)

    # (c) a simple POST. theme="cave" is rejected 400 before any build, so this
    # stays fast and writes nothing; we assert only on the CORS headers of
    # whatever status comes back, never requiring a 200.
    post_resp = _FOREIGN_CLIENT.post(
        "/api/generate",
        json={"theme": "cave", "rooms": ROOMS},
        headers={"Origin": origin},
    )
    _assert_no_cors_grant(post_resp, origin)


# ---------------------------------------------------------------------------
# Build identity — /api/version + build_commit on generate
# ---------------------------------------------------------------------------
#
# Regression guard for a stale-server debugging session: the server runs with
# reload=False, so the UI must be able to tell which code is loaded and whether
# the source on disk has moved on since startup.

VERSION_KEYS = {
    "commit", "short", "branch", "dirty", "started_at", "source_fingerprint",
    "current_commit", "current_fingerprint", "stale",
}


def test_version_reports_loaded_build(client):
    """/api/version returns the build identity, echoes an allowed Origin like
    the other GET routes, and is not stale in a fresh process."""
    origin = "http://localhost:5173"
    resp = assert_no_wildcard(client.get("/api/version", headers={"Origin": origin}))
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin

    body = resp.json()
    assert VERSION_KEYS <= set(body), f"missing keys: {VERSION_KEYS - set(body)}"
    assert isinstance(body["short"], str)
    assert body["short"] == "unknown" or len(body["short"]) == 7
    if body["commit"] != "unknown":
        assert body["commit"].startswith(body["short"])
    assert isinstance(body["dirty"], bool)
    assert body["stale"] is False
    assert body["current_commit"] == body["commit"]
    assert body["current_fingerprint"] == body["source_fingerprint"]


def test_version_stale_when_source_changes(client, monkeypatch):
    """An edit after startup (fingerprint moves) flags the server stale."""
    monkeypatch.setattr(app_mod, "_source_fingerprint", lambda: "edited000000")
    body = assert_no_wildcard(client.get("/api/version")).json()
    assert body["stale"] is True
    assert body["current_fingerprint"] == "edited000000"
    assert body["source_fingerprint"] == app_mod.BUILD_INFO["source_fingerprint"]


def test_version_stale_when_head_moves(client, monkeypatch):
    """A new commit/checkout after startup (HEAD moves) flags the server stale."""
    monkeypatch.setattr(app_mod, "_current_commit", lambda: "f" * 40)
    body = assert_no_wildcard(client.get("/api/version")).json()
    assert body["stale"] is True
    assert body["current_commit"] == "f" * 40


def test_generate_reports_build_commit(client):
    """The generate response carries the loaded short commit (build_commit)."""
    resp = assert_no_wildcard(
        client.post(
            "/api/generate",
            json={"theme": "dungeon", "rooms": ROOMS, "seed": PINNED_SEED},
        )
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["build_commit"] == app_mod.BUILD_INFO["short"]
