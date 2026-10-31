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

import json
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
# 10.2 — EQ_PATH refusal: importing server.app with an overlapping EQ_PATH
# must raise, so the server never starts (task 19.5).
# ---------------------------------------------------------------------------

def test_import_refuses_when_eq_path_overlaps_output(tmp_path):
    """Importing ``server.app`` with EQ_PATH containing OUTPUT_DIR raises.

    ``assert_output_allowed(OUTPUT_DIR, env_value("EQ_PATH"))`` runs at IMPORT
    time, before ``OUTPUT_DIR.mkdir`` — so an EQ_PATH that contains the output
    tree makes the import raise ``OutsideOutputError`` and uvicorn can never
    load the app. We run the import in a fresh subprocess (the module is already
    imported in-process) with EQ_PATH pointed at the repo root, which contains
    the server's ``output/web`` OUTPUT_DIR.
    """
    import subprocess
    import sys
    from pathlib import Path as _P

    repo_root = _P(app_mod.__file__).resolve().parent.parent
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["EQ_PATH"] = str(repo_root)   # contains output/web -> overlap

    proc = subprocess.run(
        [sys.executable, "-c", "import server.app"],
        cwd=str(repo_root), env=env, capture_output=True, text=True,
    )
    assert proc.returncode != 0, "import should fail with an overlapping EQ_PATH"
    assert "OutsideOutputError" in proc.stderr, proc.stderr


def test_import_ok_when_eq_path_disjoint(tmp_path):
    """Importing ``server.app`` with a disjoint (or unset) EQ_PATH succeeds.

    The refusal must not disturb the normal case: a disjoint EQ_PATH (and, by
    construction, an unset one) leaves the import working so the test suite's
    own ``import server.app`` keeps functioning (task 19.5).
    """
    import subprocess
    import sys
    from pathlib import Path as _P

    repo_root = _P(app_mod.__file__).resolve().parent.parent
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["EQ_PATH"] = str(tmp_path / "somewhere_else")   # disjoint

    proc = subprocess.run(
        [sys.executable, "-c", "import server.app; print('ok')"],
        cwd=str(repo_root), env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


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
# M0 6.7 — controls path rejects the removed "cave" zone type
# ---------------------------------------------------------------------------

def test_controls_cave_zone_type_rejected(client):
    """A control-driven generate with zone_type="cave" is a 400 whose detail
    names the ENABLED zone types, and nothing is written to OUTPUT_DIR.

    After the wave-4 gate (task 15.5) the controls path refuses any zone type
    whose canonical form is not in ``ENABLED_ZONE_TYPES`` — ``cave`` is
    undefined (canonicalises to None) and is refused, listing the enabled set
    (``dungeon, city, wilderness``) (Req 3.3)."""
    resp = assert_no_wildcard(
        client.post("/api/generate", json={"zone_type": "cave", "rooms": ROOMS})
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    for zt in ("dungeon", "city", "wilderness"):
        assert zt in detail, f"detail does not name enabled {zt!r}: {detail!r}"
    # The 400 is raised before the factory runs, so no artifacts are produced.
    assert list(app_mod.OUTPUT_DIR.iterdir()) == []


# ---------------------------------------------------------------------------
# Req 11.4 — the legacy /api/themes endpoint is a pure alias of /api/zone_types
# ---------------------------------------------------------------------------

def test_zone_types_and_themes_listings_are_identical(client):
    """``GET /api/zone_types`` and the legacy ``GET /api/themes`` return the
    SAME body (Req 11.4).

    ``/api/themes`` is the kept legacy LOAD boundary on the server's read side:
    an old client polling it must get exactly what the current endpoint serves,
    so the two bodies are byte-for-byte equal and both list the Defined zone
    types.
    """
    zt = assert_no_wildcard(client.get("/api/zone_types"))
    th = assert_no_wildcard(client.get("/api/themes"))
    assert zt.status_code == 200, zt.text
    assert th.status_code == 200, th.text
    assert zt.json() == th.json(), (
        "/api/themes body diverged from /api/zone_types: "
        f"{th.json()!r} != {zt.json()!r}"
    )
    # The listing is one {name, enabled, reason} object per Defined zone type,
    # in canonical order; wave 4 (task 15.5) replaced the bare name list.
    listing = zt.json()["zone_types"]
    assert [z["name"] for z in listing] == ["dungeon", "city", "wilderness"]
    by_name = {z["name"]: z for z in listing}
    assert by_name["dungeon"]["enabled"] is True
    assert by_name["city"]["enabled"] is True
    assert by_name["wilderness"] == {"name": "wilderness", "enabled": True,
                                     "reason": None}

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


@settings(max_examples=scaled(100), deadline=None)
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


# ---------------------------------------------------------------------------
# Per-build file route traversal guards (task 15.9, Req 4.2 / 4.3)
# ---------------------------------------------------------------------------
#
# The /api/zones/{zone_id}/{version}/{filename} route (task 15.5) is strict:
# every segment must match SEGMENT_RE and not be "..", the extension must be in
# BUILD_FILE_EXTS, and the resolved path must stay inside OUTPUT_DIR. A
# malformed segment or a disallowed extension is a 400; a well-formed request
# for a file that isn't there is a 404. These are example tests covering those
# cases on the route the 15.5 implementation actually exposes.

class TestZoneFileGuards:
    def test_disallowed_extension_is_400(self, client):
        """A well-formed path whose extension is not in the allow-list is a 400,
        before any file access (Req 4.3)."""
        for filename in ("evil.py", "notes.txt", "data.jsonl"):
            resp = assert_no_wildcard(
                client.get(f"/api/zones/gen_abc/v1/{filename}")
            )
            assert resp.status_code == 400, f"{filename!r} -> {resp.status_code}: {resp.text}"

    def test_bad_path_segment_is_400(self, client):
        """A segment with a character outside SEGMENT_RE (here a space / a
        slash-escaped parent hop) is rejected 400, never reaching the file
        system (Req 4.3)."""
        # A space is outside [A-Za-z0-9_.-]; the allow-list ext keeps the refusal
        # about the segment, not the extension.
        resp = assert_no_wildcard(
            client.get("/api/zones/bad%20id/v1/bad%20id.glb")
        )
        assert resp.status_code == 400, resp.text

        # A URL-encoded parent-dir hop (%2e%2e == "..") as a segment is refused:
        # the `== ".."` guard (and the resolve-and-recheck) block traversal.
        resp = assert_no_wildcard(
            client.get("/api/zones/gen_abc/%2e%2e/gen_abc.glb")
        )
        assert resp.status_code == 400, resp.text

    def test_absent_wellformed_file_is_404(self, client):
        """A well-formed request (good segments, allowed extension) for a file
        that does not exist is a 404, not a 400 (Req 4.2)."""
        resp = assert_no_wildcard(
            client.get("/api/zones/gen_missing/v1/gen_missing.glb")
        )
        assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Mode routing + per-field validation (task 17.6, Req 1.1, 1.3, 2.5, 8.1)
# ---------------------------------------------------------------------------
#
# These are deterministic EXAMPLE tests (not property tests) over the mode
# resolution and body validation the 17.5 server exposes. They use the shared
# ``client`` fixture, which points OUTPUT_DIR at an isolated tmp dir — so the
# "nothing written on a 400" assertions (``OUTPUT_DIR`` empty afterwards) are
# reliable: a rejected request must leave the per-build output tree untouched.

# A prompt that the rule planner turns into a small dungeon (verified: zone_type
# "dungeon", room_count 3), so a prompt-mode build is the same small, gate-
# passing 3-room dungeon the controls/legacy path uses with PINNED_SEED.
DUNGEON_PROMPT = "a dungeon with 3 rooms"


def _output_is_empty():
    """True when the (tmp) OUTPUT_DIR holds no artifacts — the post-400 state."""
    return list(app_mod.OUTPUT_DIR.iterdir()) == []


class TestModeRouting:
    """The mode routing table (Req 1.1): the resolved mode is explicit-wins,
    else inferred from a non-empty prompt, and the response ``mode`` reflects
    the resolved mode in every case."""

    def test_explicit_prompt_mode_builds_from_prompt(self, client):
        """mode="prompt" with a prompt -> prompt build; response mode=prompt,
        and the planner/plan provenance is present (prompt path)."""
        resp = assert_no_wildcard(
            client.post("/api/generate",
                        json={"mode": "prompt", "prompt": DUNGEON_PROMPT,
                              "seed": PINNED_SEED})
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["mode"] == "prompt"
        assert body["source"] == "prompt"
        # Prompt provenance: a planner ran and produced a plan.
        assert body["planner"] is not None
        assert body["plan"] is not None
        assert body["zone_type"] == "dungeon"

    def test_explicit_controls_mode_builds_from_controls(self, client):
        """mode="controls" with a controls sub-object -> controls build;
        response mode=controls, no planner ran."""
        resp = assert_no_wildcard(
            client.post("/api/generate",
                        json={"mode": "controls",
                              "controls": {"zone_type": "dungeon",
                                           "room_count": ROOMS},
                              "seed": PINNED_SEED})
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["mode"] == "controls"
        assert body["source"] == "controls"
        assert body["planner"] is None
        assert body["zone_type"] == "dungeon"
        assert body["rooms"] == ROOMS

    def test_absent_mode_with_prompt_infers_prompt(self, client):
        """mode absent + a non-empty prompt -> inferred prompt mode; response
        mode=prompt."""
        resp = assert_no_wildcard(
            client.post("/api/generate",
                        json={"prompt": DUNGEON_PROMPT, "seed": PINNED_SEED})
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["mode"] == "prompt"
        assert body["planner"] is not None

    def test_absent_mode_without_prompt_infers_controls(self, client):
        """mode absent + no prompt -> inferred controls mode (the on-load /
        dropdown path); response mode=controls, no planner."""
        resp = assert_no_wildcard(
            client.post("/api/generate",
                        json={"zone_type": "dungeon", "rooms": ROOMS,
                              "seed": PINNED_SEED})
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["mode"] == "controls"
        assert body["planner"] is None

    def test_mode_present_in_response(self, client):
        """Every generate response carries a resolved ``mode`` field (Req 1.1)."""
        resp = assert_no_wildcard(
            client.post("/api/generate",
                        json={"zone_type": "dungeon", "rooms": ROOMS,
                              "seed": PINNED_SEED})
        )
        assert resp.status_code == 200, resp.text
        assert "mode" in resp.json()


class TestModeRejections:
    """400s raised before any build/write: unknown mode and an empty prompt in
    prompt mode (Req 1.3). Each leaves OUTPUT_DIR empty."""

    def test_unknown_mode_is_400(self, client):
        """mode="banana" (not prompt|controls) is a 400, nothing written."""
        resp = assert_no_wildcard(
            client.post("/api/generate",
                        json={"mode": "banana", "prompt": DUNGEON_PROMPT})
        )
        assert resp.status_code == 400, resp.text
        # The detail names the valid modes.
        detail = resp.json()["detail"]
        assert "prompt" in detail and "controls" in detail, detail
        assert _output_is_empty()

    def test_empty_prompt_in_prompt_mode_is_400(self, client):
        """mode="prompt" with an empty/blank prompt is a 400, nothing written
        (Req 1.3)."""
        for prompt in ("", "   "):
            resp = assert_no_wildcard(
                client.post("/api/generate",
                            json={"mode": "prompt", "prompt": prompt})
            )
            assert resp.status_code == 400, f"{prompt!r} -> {resp.text}"
            assert _output_is_empty()


class TestNonIntegerFieldRejections:
    """A non-integer value of any kind fed to an integer field is a 400 that
    NAMES the field, before any build/write (Req 2.5). ``seed`` and ``rooms``
    are StrictInt (rejected by the RequestValidationError -> 400 handler);
    ``controls.room_count`` / ``controls.locks`` are rejected by ``_require_int``.

    A JSON ``bool`` is an ``int`` subclass in Python but must still be rejected
    (StrictInt and ``_require_int`` both refuse it) — otherwise ``true`` would
    silently build one room.

    ``null`` is split out: ``seed`` is ``Optional[StrictInt]`` so a ``null``
    seed is the documented "omit for random" sentinel (a 200, covered by
    ``test_seed_null_is_random_not_400``), while a ``null`` on the controls
    numeric fields is a supplied non-integer and is refused 400 by
    ``_require_int`` (otherwise ``ZonePlan.validate`` would ``int(None)`` and
    500) — so those keep ``None`` in their matrix."""

    # Kinds every integer field must refuse via its StrictInt / _require_int
    # guard. ``True``/``False`` cover the bool-is-an-int-subclass trap.
    NON_INT_KINDS = (3.5, "7", True, False, [1, 2])
    # Controls numeric fields additionally refuse a present ``null`` (seed does
    # not — see test_seed_null_is_random_not_400).
    CONTROLS_NON_INT_VALUES = NON_INT_KINDS + (None,)

    def _assert_names_field_400(self, client, payload, field):
        resp = assert_no_wildcard(client.post("/api/generate", json=payload))
        assert resp.status_code == 400, f"{payload!r} -> {resp.text}"
        assert field in resp.json()["detail"], (
            f"400 detail must name {field!r}: {resp.json()['detail']!r}"
        )
        assert _output_is_empty()

    @pytest.mark.parametrize("value", NON_INT_KINDS)
    def test_seed_non_integer_is_400(self, client, value):
        """A non-integer ``seed`` (StrictInt) is a 400 naming ``seed``."""
        self._assert_names_field_400(
            client, {"zone_type": "dungeon", "rooms": ROOMS, "seed": value},
            "seed")

    def test_seed_null_is_random_not_400(self, client):
        """``seed: null`` is the documented "omit for random" sentinel
        (``Optional[StrictInt]``): a 200 with a server-chosen seed, NOT a 400
        (Req 2.5 bounds the seed *kind* and range for a PINNED seed; an absent
        pin is legal)."""
        resp = assert_no_wildcard(
            client.post("/api/generate",
                        json={"zone_type": "dungeon", "rooms": ROOMS,
                              "seed": None})
        )
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json()["seed"], int)

    @pytest.mark.parametrize("value", CONTROLS_NON_INT_VALUES)
    def test_controls_room_count_non_integer_is_400(self, client, value):
        """A non-integer ``controls.room_count`` (_require_int) is a 400 naming
        ``room_count`` — including a present ``null``."""
        self._assert_names_field_400(
            client,
            {"mode": "controls",
             "controls": {"zone_type": "dungeon", "room_count": value}},
            "room_count")

    @pytest.mark.parametrize("value", CONTROLS_NON_INT_VALUES)
    def test_controls_locks_non_integer_is_400(self, client, value):
        """A non-integer ``controls.locks`` (_require_int) is a 400 naming
        ``locks`` — including a present ``null``."""
        self._assert_names_field_400(
            client,
            {"mode": "controls",
             "controls": {"zone_type": "dungeon", "room_count": ROOMS,
                          "locks": value}},
            "locks")


# ---------------------------------------------------------------------------
# Req 8.1 — a legacy target field is ignored, not honoured
# ---------------------------------------------------------------------------

def test_target_shortname_is_ignored(client):
    """A request carrying the forbidden/legacy ``target_shortname: "arena"``
    returns 200 (the field is dropped via ``extra="ignore"``), and every build
    file is named by the generated ``<id>`` — never "arena" (Req 8.1)."""
    resp = assert_no_wildcard(
        client.post("/api/generate",
                    json={"zone_type": "dungeon", "rooms": ROOMS,
                          "seed": PINNED_SEED, "target_shortname": "arena"})
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    zone_id = body["id"]
    assert zone_id != "arena"

    # The returned URLs are named by the zone id, not the legacy target.
    for url_field in ("glb_url", "zone_url", "map_url"):
        url = body[url_field]
        assert zone_id in url, f"{url_field} ({url}) is not named by the id"
        assert "arena" not in url, f"{url_field} ({url}) leaked the target name"

    # On disk the build directory and every artifact is <id>.*; nothing is
    # named "arena".
    build_dir = app_mod.OUTPUT_DIR / zone_id / "v1"
    assert build_dir.is_dir(), f"missing build dir {build_dir}"
    subdirs = [d.name for d in build_dir.iterdir() if d.is_dir()]
    assert set(subdirs) <= {"maps"}, f"unexpected subdirectories: {subdirs}"
    produced = [f for f in build_dir.rglob("*") if f.is_file()]
    assert produced, "no artifacts written"
    for f in produced:
        assert f.name.startswith((f"{zone_id}.", f"{zone_id}_")), (
            f"artifact not named by the id: {f.name}"
        )
        assert "arena" not in f.name, f"artifact leaked the target name: {f.name}"


# ---------------------------------------------------------------------------
# Wilderness map edges in controls mode (wilderness spec task 3)
# ---------------------------------------------------------------------------

def test_controls_edges_reach_the_wilderness_build(client):
    """``controls.edges`` declares the Rim; the built zone carries it (and the
    zoneline/river regions it implies)."""
    resp = client.post("/api/generate", json={
        "mode": "controls", "seed": 2024,
        "controls": {"zone_type": "wilderness",
                     "edges": {"N": "zoneline", "e": "river"}},
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["zone_type"] == "wilderness" and body["validated"]
    build_dir = app_mod.OUTPUT_DIR / body["id"] / "v1"
    assert (build_dir / f"{body['id']}.zone.json").exists()
    # The materials count reflects the extra zoneline + water region kinds.
    assert body["materials"] >= 5


@pytest.mark.parametrize("controls, needle", [
    ({"zone_type": "wilderness", "edges": {"Q": "river"}}, "side"),
    ({"zone_type": "wilderness", "edges": {"N": "lake"}}, "type"),
    ({"zone_type": "wilderness", "edges": ["N", "river"]}, "object"),
    ({"zone_type": "dungeon", "edges": {"N": "river"}}, "wilderness"),
])
def test_bad_edges_are_a_400_naming_the_field(client, controls, needle):
    resp = client.post("/api/generate",
                            json={"mode": "controls", "controls": controls})
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert "edges" in detail and needle in detail, detail
    assert list(app_mod.OUTPUT_DIR.iterdir()) == []


def test_zone_types_lists_wilderness_as_enabled(client):
    listing = client.get("/api/zone_types").json()["zone_types"]
    wild = next(z for z in listing if z["name"] == "wilderness")
    assert wild == {"name": "wilderness", "enabled": True, "reason": None}


# ---------------------------------------------------------------------------
# M2 task 8 — build files under maps/, HEAD, and artifact URLs (M2 Req 9)
# ---------------------------------------------------------------------------

import re  # noqa: E402
from pathlib import Path  # noqa: E402
from urllib.parse import quote  # noqa: E402

from hypothesis import strategies as st  # noqa: E402

_P18_NAME = "gen_t"
# The pre-built build dir's files (relative to OUTPUT_DIR). Besides a full
# build it holds files the rules must refuse even though they exist: a root
# ``.txt``, a ``.py``, a plain ``.json``/``.svg``, another subfolder, and a
# servable-looking file outside any build dir.
_P18_FILES = [
    f"{_P18_NAME}/v1/{_P18_NAME}.eqg", f"{_P18_NAME}/v1/{_P18_NAME}.glb",
    f"{_P18_NAME}/v1/{_P18_NAME}.zone.json", f"{_P18_NAME}/v1/{_P18_NAME}.map.svg",
    f"{_P18_NAME}/v1/{_P18_NAME}.png",
    f"{_P18_NAME}/v1/maps/{_P18_NAME}.txt", f"{_P18_NAME}/v1/maps/{_P18_NAME}_1.txt",
    f"{_P18_NAME}/v1/notes.txt", f"{_P18_NAME}/v1/{_P18_NAME}.py",
    f"{_P18_NAME}/v1/{_P18_NAME}.json", f"{_P18_NAME}/v1/{_P18_NAME}.svg",
    f"{_P18_NAME}/v1/other/{_P18_NAME}.txt", f"{_P18_NAME}/v1/maps/{_P18_NAME}.glb",
    f"{_P18_NAME}/{_P18_NAME}.glb", "secret.glb",
]
_ROOT_EXTS = (".eqg", ".glb", ".zone.json", ".map.svg", ".png", ".sql", ".zip")
_ALL_EXTS = _ROOT_EXTS + (".txt", ".json", ".svg", ".py", ".jsonl", "", ".GLB", ".TXT")
_WIN_RESERVED = re.compile(r"(?i)^(con|prn|aux|nul|com\d|lpt\d)(\..*)?$")


def _p18_junk():
    """Segments the rules must refuse: parent hops, unicode, separator-free
    junk and dotted tricks (``/`` is left out: it would split the segment)."""
    return st.one_of(
        st.sampled_from(["..", ".", "...", "a..b.glb", "a b.glb", "é.glb",
                         "%2e%2e", "gen_t.glb.", "~gen_t.glb"]),
        st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="/"),
                min_size=1, max_size=12),
    ).filter(lambda s: not _WIN_RESERVED.match(s))


def build_paths():
    """Build-file paths below ``/api/zones/``: 3 segments, or 4 with a
    subfolder, drawn from valid names, the allow-list extensions, ``..``,
    unicode, empty-extension and bad-extension names (design "build_paths")."""
    filename = st.one_of(
        st.builds(lambda stem, ext: stem + ext,
                  st.sampled_from([_P18_NAME, f"{_P18_NAME}_1", f"{_P18_NAME}_2",
                                   "notes", "GEN_T", "x"]),
                  st.sampled_from(_ALL_EXTS)),
        _p18_junk(),
    )
    zone = st.one_of(st.sampled_from([_P18_NAME, "gen_other"]), _p18_junk())
    version = st.one_of(st.sampled_from(["v1", "v2"]), _p18_junk())
    subdir = st.one_of(st.none(), st.sampled_from(["maps", "other", "MAPS"]), _p18_junk())
    return st.builds(
        lambda z, v, d, f: (z, v, f) if d is None else (z, v, d, f),
        zone, version, subdir, filename)


def _p18_url(parts) -> str:
    """Percent-encode each segment; all-dot segments as ``%2E`` so the client
    does not collapse them before they reach the server."""
    enc = [quote(p, safe="") if p.strip(".") else p.replace(".", "%2E") for p in parts]
    return "/api/zones/" + "/".join(enc)


def _p18_expected(out: Path, parts):
    """The Req 9.3 / 9.2 model: (status, bytes or None)."""
    seg_ok = all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) and ".." not in p and p != "."
                 for p in parts)
    if not seg_ok:
        return 400, None
    if len(parts) == 4 and parts[2] != "maps":
        return 400, None
    exts = (".txt",) if len(parts) == 4 else _ROOT_EXTS
    if not parts[-1].lower().endswith(exts):
        return 400, None
    build_dir = (out / parts[0] / parts[1]).resolve()
    target = (build_dir / Path(*parts[2:])).resolve()
    if build_dir not in target.parents:
        return 400, None
    if not target.is_file():
        return 404, None
    return 200, target.read_bytes()


def test_build_file_paths_served_or_refused(tmp_path, monkeypatch):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 18 (M2-P12):
    Build-file paths are served or refused by the rules.

    Over one pre-built directory, a GET is 400 (no body) exactly when Req 9.3
    rejects the path, else 200 with the file's exact bytes when it exists, else
    404 with no body; HEAD gives the same status and headers and no body.
    """
    out = tmp_path / "web_out"
    for i, rel in enumerate(_P18_FILES):
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(f"{rel}\n{i}\n".encode())
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    client = TestClient(app_mod.app)

    @settings(max_examples=scaled(200), deadline=None)
    @given(parts=build_paths())
    def check(parts):
        url = _p18_url(parts)
        status, data = _p18_expected(out, parts)
        got = client.get(url)
        assert got.status_code == status, (parts, url, got.status_code)
        assert got.content == (data if status == 200 else b""), (parts, url)
        head = client.head(url)
        assert head.status_code == status, (parts, url)
        assert head.content == b""
        assert dict(head.headers) == dict(got.headers), (parts, url)

    check()


def test_maps_route_serves_exact_bytes_as_text(client):
    """A ``maps/`` GET of an existing ``.txt`` returns its exact bytes as
    ``text/plain`` (M2 Req 9.1); HEAD matches GET's headers with no body
    (Req 9.4)."""
    data = b"L 1.0, 2.0, 0.0, 3.0, 4.0, 0.0, 0, 0, 0\r\nP 0, 0, 0, 0, 0, 0, 2, Gate_A\r\n"
    maps = app_mod.OUTPUT_DIR / "gen_x" / "v1" / "maps"
    maps.mkdir(parents=True)
    (maps / "gen_x_1.txt").write_bytes(data)

    url = "/api/zones/gen_x/v1/maps/gen_x_1.txt"
    resp = client.get(url)
    assert resp.status_code == 200, resp.text
    assert resp.content == data
    assert resp.headers["content-type"] == "text/plain; charset=us-ascii"
    head = client.head(url)
    assert head.status_code == 200 and head.content == b""
    assert dict(head.headers) == dict(resp.headers)


def test_generate_lists_artifacts_with_live_urls(client):
    """A generate response lists ``map_svg``, ``eqg``, ``glb``, ``sidecar`` and
    every ``eqmap`` file the build wrote (with its layer), and every URL GETs
    200 with the file's bytes (M2 Req 9.5). ``map_url`` and ``eqg_url`` stay."""
    resp = client.post("/api/generate",
                       json={"theme": "dungeon", "rooms": ROOMS, "seed": PINNED_SEED})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    name, arts = body["id"], body["artifacts"]
    build_dir = app_mod.OUTPUT_DIR / name / "v1"

    kinds = [a["kind"] for a in arts]
    for kind in ("map_svg", "eqg", "glb", "sidecar"):
        assert kinds.count(kind) == 1, kinds
    eqmaps = [a for a in arts if a["kind"] == "eqmap"]
    written = sorted(p.name for p in (build_dir / "maps").glob("*.txt"))
    assert written, "the pinned build wrote no EQ map files"
    assert sorted(a["filename"] for a in eqmaps) == [f"maps/{n}" for n in written]
    # Every map file the Sidecar records is listed.
    sidecar = json.loads((build_dir / f"{name}.zone.json").read_text())
    assert set(sidecar["map_files"]) <= {a["filename"] for a in arts}
    assert [a["layer"] for a in eqmaps] == sorted(a["layer"] for a in eqmaps)
    assert eqmaps[0]["layer"] == 0 and eqmaps[0]["filename"] == f"maps/{name}.txt"
    assert all(a["layer"] is None for a in arts if a["kind"] != "eqmap")

    for a in arts:
        assert a["url"] == f"/api/zones/{name}/v1/{a['filename']}"
        got = client.get(a["url"])
        assert got.status_code == 200, (a, got.status_code)
        assert got.content == (build_dir / a["filename"]).read_bytes()
    by_kind = {a["kind"]: a["url"] for a in arts}
    assert body["map_url"] == by_kind["map_svg"]
    assert body["eqg_url"] == by_kind["eqg"]
