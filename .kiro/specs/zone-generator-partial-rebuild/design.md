# Design — zone-generator-partial-rebuild (roadmap step 16)

Written at master `56b14c5`. Verify against the code before you rely on a line here.

## Where things are

- `server/app.py`: `POST /api/generate` plans a ZonePlan (prompt or controls), makes a spec
  factory (`plan_to_spec`) and calls `generators.pipeline.generate_validated(...,
  zone_id=new_zone_id(), version=1)`. The build lands in `output/web/<zone>/v1/`; the file
  route `/api/zones/<zone>/<version>/<file>` serves it. `POST /api/room_decor` (step 15)
  re-decorates one room of a build.
- `generators/pipeline.py`: `generate_validated` builds into a scratch folder, gates it
  (`_traversal_report`: `analyzer.traverse.validate`, or the outdoor-dungeon and wilderness
  reports), checks the format (`check_eqg`), rerolls a blamed stage on failure (`_blame`), and
  on a pass moves the files into `v<version>/` (`_finalize_build`, `_write_map_artifacts`,
  `_write_handoffs`).
- `generators/builder.py`: `ZoneBuilder.build` makes the TER (`_build_geometry`), then Sites,
  trees, Attachments, Decor (`decor_for`, with `BareCap` and `settle_room`), the ZON, the
  textures, the `.eqg`, the sidecar and the GLB.
- `analyzer/traverse.py` `validate`: `build_walk_surface(ter)` (about 3 s on the 16-room
  dungeon), the reached faces, `outline_checks`, then the placed models through
  `analyzer.footprints.check_room_props(surf, reached, spec, placed, mesh, seed_face)`, then
  `corridor_continuity`. Only `check_room_props` reads the Props.
- `generators/zone_spec.py`: `ZoneSpec.to_dict` / `from_dict` / `save` / `load`; `decor_seed`
  and `rooms_seed` are left out of the dict when unset.
- `generators/decor/room_view.py` (step 15): re-decorates one RoomContext as the build does,
  replaying the build's bare decisions.
- The page: `web/src/main.ts` (reroll buttons at "Reroll rooms" / "Reroll decor", side panel,
  map), `web/src/roomview.ts`, `web/src/api.ts`.

## Versions

A rebuild writes `v<n+1>` of the same zone. The pipeline already takes `version`; the Server
picks the next free number under `output/web/<zone>/` and passes it. Two rebuilds of one zone
at once must not take the same number: take it under a per-zone lock, or create the folder
exclusively and retry.

Saved with every version (Req 1.4), written in `_finalize_build`'s move like the hand-offs:

- `<name>.request.json`: the GenerateRequest as the Server resolved it (mode, prompt or
  controls, the resolved `seed`, `rooms_seed`, `decor_seed`, `decor_layers`, and
  `room_decor_seeds`).
- `<name>.spec.json`: `ZoneSpec.save`, plus the decor layers (they ride beside the spec, not in
  it: `with_decor_layers`).

The sidecar gains `version: {n, parent, changed, how}` on v2 and later. `GET
/api/zones/<zone>/versions` reads each `v*/` folder's sidecar (`version` block, `seeds`,
mtime, `took_ms`) and answers them in order.

## Rebuild

`POST /api/rebuild {zone, version, decor_seed?, rooms_seed?, room_decor?}`:

1. Read the parent's `request.json` (404 if the version or file is missing).
2. Apply the change. `rooms_seed` → **full**: plan again from the request with the new seed
   (the existing Generate path, given the zone id and version). `decor_seed` or
   `room_decor: {room, decor_seed}` → **partial** (below). `room_decor` adds or replaces one
   entry in `room_decor_seeds`; a new `decor_seed` clears them (the zone's Props all change).
3. Answer as Generate does, plus the `version` block.

**Partial.** `generators/rebuild.py` `rebuild_decor(parent_dir, spec, changes, cache)`:

- Load the parent's spec (`spec.json`), set the new `decor_seed` / `room_decor_seeds`.
- Build with the parent's TER and textures reused: `ZoneBuilder.build` gains a way to take the
  TER bytes and the texture DDS from the parent's `.eqg` instead of making them (geometry and
  texture drawing are skipped; everything after them runs as now). Sites, trees and the World
  come from the spec as now (cheap).
- Gate: if `cache` holds the parent's shell result (below), run the Props check against it;
  else run the full gate and keep the shell result for next time.
- Format check, map files (outline from the cache), finalize into `v<n+1>`.

**Proof (Req 2.3).** A partial rebuild and a full Generate of the parent's request with the same
seeds give the same `.eqg` bytes (footer aside) and the same sidecar but the `version` block and
timings. Tests: the 16-room Graph dungeon seed 2, a city, an outdoor dungeon, a Theme Tomb, a
wilderness with Sites, each with a new decor seed and with one room decor seed.

## The shell's gate result

`analyzer.traverse.validate` splits into the shell part and the Props part so both callers share
one code path:

- `shell_report(ter, spec, agent, check_corridors) -> Shell`: the walk surface, the reached faces,
  the seed face, the outline checks, the corridor results, and the mesh's collidable triangles.
- `validate(...)` = `shell_report` + `check_room_props(shell..., placed)` + the merge into
  `TraversalReport`, exactly as now. No verdict changes.

A kept `Shell` belongs to one TER: key it by the TER bytes' hash (not the version), so any
version with the same TER finds it. The Server keeps a few (LRU, about 4; the 16-room shell is
tens of MB: measure it and say so). The outdoor dungeon's report runs the room gate plus the
bowl; split it the same way if its time allows, else it takes the full gate (say which in the
card's commit). The wilderness keeps its full bowl gate (Req 6.2).

The map outline (`mapgeom.extract_outline`, from the TER) is kept beside the shell, by the same
key; `_write_map_artifacts` takes it when given.

**Proof (Req 4.3).** For seeds that pass and seeds where a Prop fails the gate (force one:
a Prop over a door's Throat), the partial verdict and failures equal the full gate's.

## Room decor seeds

`ZoneSpec.room_decor_seeds: Dict[str, int]` (left out when empty). `ZonePlan` carries it too,
so a full rebuild or Generate reproduces it. In `decor_for`:

- The bare decision of every room is drawn as now, from the zone's decor seed (the `BareCap`
  order), so a room's own seed can't move another room's.
- A room with its own seed is placed with `decor_seed = room_decor_seeds[id]` in the same
  placement entry; every other room as now.

The sidecar's `seeds` block gains `room_decor_seeds` when non-empty; the room's record gains
`decor_seed`. `room_view.decorate_room` reports the seed it used and, "As built", takes the
room's own.

## The page

- Header: `v3` with ◂ ▸ (disabled at the ends) after the build line; opening a version loads its
  GLB, sidecar, map and files as a new build does, keeping the camera.
- Reroll decor → `/api/rebuild {decor_seed: fresh}`; Reroll rooms → `{rooms_seed: fresh}`. Both
  open the new version.
- Room view: **Use in zone** (enabled once the room's seed differs from what the open version
  has) → `/api/rebuild {room_decor: {room, decor_seed}}`, then reopen the room on the new version.
- Side panel: Version row (`v3 of 3 · from v2 · decor seed`).

## Order

1. Room decor seeds (spec, plan, builder, room view): alone, byte-identical with none.
2. Versions (Server, pipeline): numbering, saved inputs, `/api/rebuild` on the full path for
   every change, `/versions`. Runs beside 1.
3. Partial rebuild from the saved stages: TER and textures reused, room decor into
   `/api/rebuild`; full gate still. Proves bytes.
4. The shell kept: the gate split, the cache, the outline; proves verdicts and time.
5. The page. Runs beside 3 and 4 (it only needs 1 and 2's API).
