# Design — zone-generator-decor-rules (roadmap step 15)

Written at master `8ebca55`. Verify against the code before you rely on a line here.

## Where things are

- `generators/decor/rules.py`: `load_decor(path, tags)` reads `rooms.toml` and `sets.toml` into a
  frozen `DecorRules` (default, kinds, types, sites, every, groups, dressing, weights, controls,
  moves, set rules, zones, once), checking with step 9's `_Checker` and raising `RuleSetError`.
  `unmet`, `coverage` and kin report.
- Callers of `load_decor`: `generators/builder.py` `_decor_data()` (cached once per process),
  `generators/decor/placement.py` (a default), `scripts/decor_room.py`, `scripts/stage.py`,
  `scripts/topology_rules.py` (`check rules/decor`, `draw-decor`).
- `generators/topology/ruleset.py`: the topology layer merge to mirror (`[layer]`, `fits`,
  clash refusal, merged-set check); `rules/topology/themes.toml` the map; `docs/TOPOLOGY_RULES.md`
  the guide to mirror.
- `scripts/decor_room.py`: decorates one RoomContext and writes a GLB of the room alone (floor,
  Spine and Throats tinted, walls, Features, POI markers, Props from the install or as boxes)
  plus `.decor.json`.
- A build folder (`output/web/<id>/v<n>/`) holds `<name>.rooms.json` (the RoomContexts, step 12)
  and the sidecar (`rooms[].props`, `dressing`, `decor_drops`; `decor` block).
- The page: `web/src/main.ts` (side panel, map dialog), `web/src/scene.ts` (the zone's scene),
  `web/src/api.ts` (types). Step 14 reshapes the header, Controls and side panel first.

## Decor layers

**Files.** `rules/decor/layers/<name>.toml`:

```toml
[layer]
name        = "tomb"
description = "Befallen's look: bones and debris, almost no light"

[weights.themes.tomb]
light = 0.1
debris = 2.5

[types.ossuary]
props = [ ... ]

[types.barracks]          # a base recipe, extended
mode  = "add"
props = [ { kind = "skull", at = "scatter", count = [1, 2] } ]
```

**Merge.** `load_decor(path, tags, layers=())` reads the base as today into raw tables, then for
each layer in order: check the file on its own (same `_Checker`, file name its own), then merge
its raw tables into the base's: a new key is added; an existing key is refused naming both files,
unless the layer entry has `mode = "add"` (lines appended; for `weights`, its Categories added,
clashing Categories refused) or `mode = "replace"`. The merged raw tables then go through the
same parsing as today, so a merged set is checked exactly as the base is, and `DecorRules` stays
the one type every caller reads. With no layers the parse is today's: bytes stay (Req 6.1).

**Theme map.** `rules/decor/themes.toml`: `tomb = { layers = ["tomb"] }`; optional
`[races]` table the same way. The layers a build takes: the theme's, then the race's, then the
request's `decor_layers`, de-duplicated keeping the first.

**Caching.** `_decor_data()` caches one `DecorRules` per tuple of layer names. The room view's
route reads fresh each call (Req 4.1) and does not touch the build cache.

## Through the build

`ZonePlan.decor_layers: Tuple[str, ...] = ()` (validated against the folder: unknown → error
naming the known), the CLI's `--decor-layer` (append), `GenerateRequest.controls.decor_layers`,
`/api/controls` gaining `decor_layers: [{name, description}]`, the builder loading by the theme
map plus the plan's, and the sidecar's `decor.layers`. Nothing reaches the World or rooms stages:
only Decor reads it, so a `decor_layers` change rebuilds identical geometry.

## The worked example

Move the tomb theme's decor from `rooms.toml` to `layers/tomb.toml`: `[weights.themes.tomb]` and
the recipes only tombs reach (check with `coverage` which room types the tomb theme's rooms take:
ossuary, ritual chamber, and others), mapped `tomb = { layers = ["tomb"] }`. A tomb build loads
base + tomb and must give identical `DecorRules` to today's (dataclass equality, a test) and
identical bytes (the tomb case of the decor goldens).

## The room view

**Module.** `generators/decor/room_view.py`: `decorate_room(contexts, room_id, *, seed, control,
layers, eq_path) -> (glb_bytes, report)`, holding what `scripts/decor_room.py` does today (that
script becomes a thin CLI on it). The report: `props` (each with `line`, `step`, `at`, `key`,
`kind`, `category`, position), `pois` (purpose, position, Dressing names), `drops` (line, what,
reason), `seed`, `control`, `layers`, `took_ms`.

**Same Props as the build (Req 4.2).** The build decorates each RoomContext with a stream salted
by the decor seed and the room; the route must reproduce that exactly: call the same placement
entry the builder calls, with the same seed derivation. A test: for the decor goldens' builds,
the route's Props for each room equal the sidecar's `rooms[].props`.

**Route.** `POST /api/room_decor` `{zone, version, room, decor_seed?, control?, decor_layers?}`
→ JSON report with a `glb_url` (written under the build folder, `room_<room>_<hash>.glb`, served
by the build-file route). Paths through `core/paths` and `_safe_segment` (lessons-learned
`fullmatch`). Rules read fresh; a failing check → 400 with the errors.

**Page.** A **Room view** overlay replacing the viewport while open: its own Three.js scene and
an orbit camera (Z-up), the room GLB, POI markers, a right-hand list (by recipe line; POIs; drops)
with two-way hover highlight (Props carry their line index in the GLB node names or the report's
order), and a toolbar: ⟳ reroll, Decor, Decor rules, re-read rules, Close. Opened from a room
list in the side panel and by clicking a room on the map dialog.

## Questions decided (see `archive.md` "Decisions")

1. **What a layer may do to an existing entry.** *Recommended: refuse by default; `mode = "add"`
   or `"replace"` per entry.* Topology refuses clashes outright; decor needs extending (a theme
   adding a skull to the barracks) far more often than topology does, but silently overriding
   would make the merge order matter in ways an author can't see.
2. **How layers are chosen.** *Recommended: the theme map, plus extra layers named in the
   request (a Decor rules control).* Like the Rule set control for topology, but additive: a
   user's layer can be tried on any build without editing the map.
3. **Which theme is the worked example.** *Recommended: tomb*: it has the strongest look
   (Befallen: 1 % light, 68 % debris) and its own room types.
4. **Room view source.** *Recommended: the build's saved RoomContexts, re-decorated with rules
   read fresh*, not a rebuild: seconds, and the walls, Features and POIs stay the build's.
5. **Room view in the page or a separate tool.** *Recommended: in the page*, beside the zone
   it came from; `scripts/decor_room.py` stays for the command line.
6. **Sites in the room view.** *Recommended: rooms only in this step*; a Site's decor reads a
   SiteContext the build doesn't save yet (follow-up).
