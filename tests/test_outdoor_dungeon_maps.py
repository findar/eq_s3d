"""Outdoor-dungeon task 8: the outline, EQ map files and preview show the open
ground and the dungeon, the dungeon on its own depth band under the hill
(Req 7.2, 7.3).

The M2 depth bands already split stacked floors; these tests pin that an
outdoor dungeon's shipped files come out that way."""

import json

import numpy as np
import pytest

from generators import outdoor_dungeon as od
from generators.eqmap import map_to_world, parse_map_layer
from generators.pipeline import generate_validated
from generators.wilderness.build import build_wilderness_ter

SEEDS = (0, 4, 9, 13)
INSET = 6.0          # room-floor samples stay this far inside the walls


@pytest.fixture(scope="module", params=SEEDS)
def build(request, tmp_path_factory):
    seed = request.param
    out = tmp_path_factory.mktemp(f"odmap{seed}")
    name = f"odmap{seed}"
    vb = generate_validated(lambda s: od.outdoor_dungeon_spec(name, s),
                            zone_type="outdoor_dungeon", zone_id=name, seed=seed,
                            output_dir=out, write_glb=False, failure_log=None)
    sidecar = json.loads((vb.build_dir / f"{name}.zone.json").read_text(encoding="utf-8"))
    return vb, sidecar


def _band_of(bands, z):
    (band,) = [b for b in bands
               if (b["z_lo"] is None or z >= b["z_lo"]) and (b["z_hi"] is None or z < b["z_hi"])]
    return band["index"]


def _layers(vb, bands):
    """Each band's parsed map layer, read back from the shipped file."""
    layers = {}
    for b in bands:
        parsed = parse_map_layer((vb.build_dir / b["file"]).read_text(encoding="utf-8"),
                                 b["index"])
        assert not parsed.skipped, parsed.skipped
        layers[b["index"]] = parsed.layer
    return layers


def test_maps_cover_open_ground_and_dungeon_on_separate_bands(build):
    """Every band has its own map file; each room's floor lies on a band of
    its own, apart from the ground above it, and the room's walls are drawn in
    that band's file."""
    vb, sidecar = build
    bands = sidecar["outline"]["bands"]
    assert len(bands) >= 2
    assert {f"maps/{b['file'].split('/')[-1]}" for b in bands} <= set(sidecar["map_files"])
    layers = _layers(vb, bands)

    spec = vb.spec
    host = build_wilderness_ter(spec, "ter_probe", 2)
    grid = od._host_grid(spec, host)
    ground = od._grid_surface(grid.z, grid.origin, grid.res)
    for room in spec.rooms:
        floor_band = _band_of(bands, room.floor_z)
        hx, hy = room.width / 2 - INSET, room.depth / 2 - INSET
        xs = np.array([room.center_x + dx for dx in (-hx, 0.0, hx) for _ in range(3)])
        ys = np.array([room.center_y + dy for _ in range(3) for dy in (-hy, 0.0, hy)])
        above = {_band_of(bands, float(z)) for z in ground(xs, ys)}
        assert floor_band not in above, (room.id, room.floor_z, above)

        x0, x1 = room.center_x - room.width / 2 - 1, room.center_x + room.width / 2 + 1
        y0, y1 = room.center_y - room.depth / 2 - 1, room.center_y + room.depth / 2 + 1

        def in_room(mx, my, mz):
            x, y, z = map_to_world(mx, my, mz)
            return x0 <= x <= x1 and y0 <= y <= y1 and abs(z - room.floor_z) < 4.0

        assert any(in_room(l.x1, l.y1, l.z1) and in_room(l.x2, l.y2, l.z2)
                   for l in layers[floor_band].lines), room.id


def test_open_ground_is_mapped_and_labels_sit_with_their_rooms(build):
    """The open ground (the spawn's band, the Main_Band) has walls of its own;
    the Entrance and Boss labels ride in the band holding their room."""
    vb, sidecar = build
    bands = sidecar["outline"]["bands"]
    layers = _layers(vb, bands)
    assert _band_of(bands, vb.spec.safe_point[2]) == 0
    assert layers[0].lines
    for room in vb.spec.rooms:
        text = {"entrance": "Entrance", "climax": "Boss"}.get(room.role)
        if text:
            band = _band_of(bands, room.floor_z)
            assert text in {l.text for l in layers[band].labels}, (room.id, band)


def test_preview_draws_both_bands_and_the_rooms(build):
    """The SVG preview traces every band's outline (one stroke colour per band)
    and draws each room's box over it."""
    vb, sidecar = build
    svg = (vb.build_dir / f"{vb.spec.name.lower()}.map.svg").read_text(encoding="utf-8")
    outline = svg.split('<g id="outline"', 1)[1].split("</g>", 1)[0]
    strokes = {s.split('"')[0] for s in outline.split('stroke="')[1:]}
    assert len(strokes) >= len(sidecar["outline"]["bands"])
    for room in vb.spec.rooms:
        assert f">{room.id}</text>" in svg
