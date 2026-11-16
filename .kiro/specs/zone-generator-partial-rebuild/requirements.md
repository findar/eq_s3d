# Requirements Document

> **STATUS: roadmap step 16, ready.** Drafted 2026-11-15 at master `56b14c5` after the user chose
> "Partial rebuild (M4)" as step 16 and agreed to the shape proposed ("Sounds good"): versions
> of one zone, rebuilding from the saved stages, re-checking only what changed, and one room's
> decor kept into the zone from the room view. Task index: `tasks.md` (card format). Decisions:
> `archive.md`.

## Introduction

Today "reroll decor" and "reroll rooms" send the last request again with one stage seed changed
and write a brand-new zone. Step 12 saves each stage's hand-off in the build folder, but nothing
reads them back. Measured at `56b14c5` on a warm Server: a 16-room Graph dungeon (seed 2) builds
in 10.7 s, an outdoor dungeon in 7.2 s, a wilderness in 2.9 s. In a fresh process the dungeon's
20 s go to the walk gate (7.8 s), Decor (5.9 s, 3.5 s of it reading the install's archives
once), the map files (2.0 s) and the GLB (1.2 s); the World, rooms and geometry are 1–2 s.

So step 16 makes a reroll a new **version of the same zone**, rebuilt from the previous
version's saved stages, re-checking only what changed; and lets a room re-decorated in the room
view (step 15) be kept into the zone. It is the "partial rebuild" piece of umbrella M4. M4's
Sessions, chat edits, the `RuleEditInterpreter` and undo/redo are not in this step; they build
on these versions later.

## Glossary

- **Version**: one build of a zone, `output/web/<zone>/v<n>/`. Version 1 is what Generate
  makes; a rebuild makes the next.
- **Parent**: the version a rebuild started from.
- **Rebuild**: making a new version from a parent with some of its inputs changed (a stage
  seed, one room's decor seed). **Partial** when it reuses the parent's saved stages; **full**
  when it plans the zone again from the parent's request.
- **Room decor seed**: a decor seed for one room, in place of the zone's for that room's Props.
- **Shell**: the zone without its Props (the TER and every non-Prop placed model).

## Requirements

### Requirement 1: Versions of one zone

**User story:** As the user polishing a zone, I want rerolls to make new versions of the same
zone, so I can step back to one I liked.

1. A rebuild writes `output/web/<zone>/v<n+1>/` beside the parent, never a new zone id. Version
   1 is unchanged: no file or sidecar key a v1 build lacked today except the saved inputs of
   Req 1.4.
2. A version's sidecar records `version: {n, parent, changed, how}`: `changed` the inputs that
   differ from the parent (`decor_seed`, `rooms_seed`, `room_decor_seeds`), `how` `"partial"`
   or `"full"`. A v1 sidecar has no `version` block.
3. `GET /api/zones/<zone>/versions` lists every version: its number, parent, changed, how, when
   and how long it took. The page can open any of them.
4. Each version saves what a rebuild needs: the request it was built from
   (`<name>.request.json`, with the resolved seeds) and its ZoneSpec (`<name>.spec.json`, with
   the decor layers it took). Every path goes through `core/paths` and `_safe_segment`.
5. A rebuild that fails the gate writes nothing and answers with the reasons, as Generate does;
   a pinned seed is never rerolled behind the user's back.

### Requirement 2: Rebuild requests

1. `POST /api/rebuild {zone, version, decor_seed?, rooms_seed?, room_decor?: {room, decor_seed}}`
   makes the next version from `version`, changing only what it names (at least one). An unknown
   zone, version or room is a 404; a bad body a 400, never a path outside the output root.
2. A changed `rooms_seed` is a full rebuild (the layout changes, so every later stage does). A
   changed `decor_seed` or `room_decor` is a partial rebuild.
3. A rebuild's `.eqg` is byte-identical (footer aside) to a full Generate of the same request
   with the same seeds and room decor seeds. Tests prove it for each zone type that takes Decor.

### Requirement 3: Room decor seeds

1. A ZoneSpec may carry `room_decor_seeds: {room_id: seed}`; empty, it is left out of the spec
   dict and every build is byte-identical to before.
2. A room with its own seed takes its Props from that seed through the same placement as the
   build; whether it is bare is still decided with the zone's decor seed (the build's bare cap),
   so no other room's Props change.
3. The sidecar's `seeds` block lists `room_decor_seeds` when there are any, and each such room's
   record names its seed.
4. The room view's report says which decor seed a room used; "As built" re-decorates with it.

### Requirement 4: Rebuilding from the saved stages

1. A partial rebuild loads the parent's ZoneSpec and reuses its TER and textures from the
   parent's `.eqg`; it runs Decor and the Pack again, and writes every artifact a build writes.
2. It re-checks only what changed: the shell's gate result (walk surface, reachability, outlines,
   corridors) is kept per version in the Server process and reused; the Props are checked
   against it as the full gate checks them. Without a kept result it runs the full gate.
3. A partial rebuild's gate verdict equals the full gate's on the same build, failures included
   (proved on seeds where a Prop fails the gate).
4. The map outline (from the TER) is reused; the map files are drawn again with the new Props.
5. Time: a decor reroll of the 16-room Graph dungeon seed 2 on a warm Server in at most 4 s
   (10.7 s today), and every partial rebuild faster than a full one of the same zone.

### Requirement 5: The page

1. The header shows the open version (`v3`) with back and forward through the zone's versions;
   opening one loads its model, sidecar, map and files.
2. **Reroll decor** makes a partial rebuild and **reroll rooms** a full one, each opening the
   new version.
3. In the room view, **Use in zone** keeps the room's current decor seed into the zone (a
   partial rebuild with `room_decor`) and opens the new version with the room view still open.
4. The side panel says which version is open, its parent and what changed.

### Requirement 6: Unchanged

1. Generate, the CLI and every build with no room decor seeds are byte-identical to before
   (the layout, Sites and decor goldens).
2. Wilderness rebuilds may take the full gate (its bowl gate judges the whole zone); they are
   still versions and still byte-identical to a full build.
