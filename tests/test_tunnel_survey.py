"""The tunnel survey's centreline recovers a synthetic bent tunnel (step 23, task 1)."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from analyzer.traverse import AgentModel  # noqa: E402
from dungeon_topology_survey import Floor  # noqa: E402
import tunnel_survey as ts  # noqa: E402


def _quad(a, b, c, d):
    return [np.array([a, b, c]), np.array([a, c, d])]


def _square(cx, cy, half):
    p = [(cx - half, cy - half, 0), (cx + half, cy - half, 0),
         (cx + half, cy + half, 0), (cx - half, cy + half, 0)]
    return _quad(*p)


def _strip(p, q, hw):
    d = (q - p) / np.linalg.norm(q - p)
    n = np.array([-d[1], d[0]]) * hw
    pts = [p + n, q + n, q - n, p - n]
    return _quad(*[(x, y, 0.0) for x, y in pts])


def _disc(c, r, sides=16):
    out = []
    for k in range(sides):
        a, b = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
        out.append(np.array([(c[0], c[1], 0.0),
                             (c[0] + r * math.cos(a), c[1] + r * math.sin(a), 0.0),
                             (c[0] + r * math.cos(b), c[1] + r * math.sin(b), 0.0)]))
    return out


def _bent_cave(headings, lengths, width=20.0, room=120.0):
    """Two square chambers joined by a tunnel of the given headings (deg) and lengths."""
    pts = [np.zeros(2)]
    for h, n in zip(headings, lengths):
        a = math.radians(h)
        pts.append(pts[-1] + n * np.array([math.cos(a), math.sin(a)]))
    tris = _square(-room / 2, 0, room / 2)
    a = math.radians(headings[-1])
    far = pts[-1] + room / 2 * np.array([math.cos(a), math.sin(a)])
    # The far room, turned square to the last leg so the tunnel meets a wall head on.
    c, s = math.cos(a), math.sin(a)
    corners = [far + np.array([c * x - s * y, s * x + c * y])
               for x, y in ((-60, -60), (60, -60), (60, 60), (-60, 60))]
    tris += _quad(*[(x, y, 0.0) for x, y in corners])
    for p, q in zip(pts, pts[1:]):
        tris += _strip(p, q, width / 2)
    for p in pts[1:-1]:
        tris += _disc(p, width / 2)
    return np.array(tris)


def test_polyline_measures_on_an_exact_bend():
    # A dense path with turns of 30 and 50 degrees: the measures are exact.
    corners = np.array([[0, 0], [60, 0], [60 + 60 * math.cos(math.radians(30)),
                                          60 * math.sin(math.radians(30))]])
    a = math.radians(-20)
    corners = np.vstack([corners, corners[-1] + 60 * np.array([math.cos(a), math.sin(a)])])
    path = np.vstack([np.linspace(p, q, 30, endpoint=False) for p, q in zip(corners, corners[1:])]
                     + [corners[-1:]])
    m = ts.polyline_measures(path, eps=1.0)
    assert np.allclose(m["turns"], [30, 50], atol=1e-6)
    assert np.allclose(m["segments"], [60], atol=1e-6)
    assert np.allclose(m["ends"], [60, 60], atol=1e-6)


@pytest.mark.parametrize("headings, lengths, turns", [
    ((0, 30, -20), (80, 70, 80), [30, 50]),
    ((0, -25, 20, -10), (70, 60, 60, 70), [25, 45, 30]),
    ((0, 80, 10), (70, 70, 70), [80, 70]),
])
def test_centreline_of_a_synthetic_bent_tunnel_recovers_its_angles(headings, lengths, turns):
    floor = Floor(_bent_cave(headings, lengths), AgentModel())
    tunnels = ts.survey(floor)
    assert len(tunnels) == 1
    t = tunnels[0]
    assert len(t["turns"]) == len(turns), t["line"]
    assert np.allclose(t["turns"], turns, atol=6), t["turns"]
    # The runs between turns are the inner legs, give or take the rounded corners.
    assert np.allclose(t["segments"], lengths[1:-1], atol=15), t["segments"]
    assert abs(np.median(t["width"]) - 20) <= ts.CELL + 1
