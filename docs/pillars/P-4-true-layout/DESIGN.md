# P-4 True-layout artifacts — design (living)

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Checked against the code at master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec).

## When maps are made

Only for an accepted build, after both gates pass ([`generators/pipeline.py`](../../../generators/pipeline.py)
`_write_map_artifacts`). A rejected attempt never gets maps. If tracing fails the build still
passes and the sidecar says `outline_unavailable` or `eqmap_unavailable`.

## The outline ([`generators/mapgeom.py`](../../../generators/mapgeom.py))

`extract_outline(ter, safe_point, ...)`:

1. **Floor faces**: standable triangles, signed so a ceiling never counts.
2. **Floor boundary**: an edge is boundary where floor coverage on one side ends, found by exact
   interval coverage (not by shared-edge topology: box corridors overlap the room floor 2 u inside
   each doorway, so a topological reading would draw a wall across every door).
3. **Classes**: a boundary with wall above is a wall line; with a drop beside it, a ledge.
4. **Merge**: collinear runs within 0.02 u join; angled lines (winding corridors) fold the same
   way. The result doesn't depend on face order (fixed in `0af5124`).
5. **Depth bands**: floors split into at most 4 bands by stacked height; a non-stacked zone is
   one Main band.

`with_solids` adds Features and placed models; `outline_summary` goes into the sidecar.

## The EQ map file ([`generators/eqmap.py`](../../../generators/eqmap.py))

- The convention is **negate and swap**: map `(mx, my, mz) = (-y, -x, z)`. It was scored against
  stock maps (all 8 sign and swap candidates, matched within 5 u), and a test pins it. It is its
  own inverse.
- Grammar `L x1, y1, z1, x2, y2, z2, r, g, b` and `P x, y, z, r, g, b, size, text`; we write the
  single-space form, 4 decimals, Windows line endings. The parser accepts the looser stock forms.
- One layer per depth band (`<name>.txt`, `_1`, `_2`, `_3`); `Entrance` and `Boss` labels in the
  band holding their room's floor; ledges take their band's colour. Lines and labels only.
- [`scripts/eqmap_preview.py`](../../../scripts/eqmap_preview.py) overlays a `.txt` on the mesh for a check without the client.

## The SVG map ([`generators/mapview.py`](../../../generators/mapview.py))

`render_map_svg(spec, outline=..., sites=..., props=...)`: the traced outline under the schematic annotations (room boxes
and ids, corridors along their real path, pacing roles, Gates and keys, Districts' hulls and
Thresholds, Sites, POIs, Props). The root carries `data-frame-a/-b/-s` (the world-to-pixel
frame) so the page can place Socket markers. Annotations sit in named groups (`outline`, `sites`, `props`, `districts`, ...) that, since [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md),
the page shows and hides as layers; the page can also draw the EQ-map view.

## On the page

[`web/src/artifacts.ts`](../../../web/src/artifacts.ts) Files panel: SVG, a 2× PNG drawn by the browser, the `.txt` layers, the
`.eqg`, the sidecar and a bundle zip, from `/api/zones/{zone}/{version}/{file}` (versioned paths,
segments checked with `fullmatch`, HTTP HEAD requests supported). [`web/src/sockets.ts`](../../../web/src/sockets.ts) reads the SVG frame.
