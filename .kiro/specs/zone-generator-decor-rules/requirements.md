# Requirements Document

> **STATUS: roadmap step 15, ready.** Drafted 2026-11-14 at master `8ebca55` from the user's
> requests the same day: "as we polish generation, i want to be able to visualize a single
> room and how it lays out decoration", then "how we define the rules for generating decor in
> rooms. i want these to be similar to the room graph rules, something that a user could write
> and plugin easily", agreeing to the shape proposed ("that sounds good"). The design's open
> questions were decided on their recommendations (`archive.md` "Decisions"). Task index:
> `tasks.md` (card format).

## Introduction

Roadmap step 15: **decor rule sets and the room view.** Step 11 put decor in data
(`rules/decor/rooms.toml`, `sets.toml`, `tags.toml`), but as one shared file: a new look means
editing it, nothing says which theme a piece serves, and nothing selects one. The graph layout's
rules (`rules/topology/`) already have the shape the user wants: base sets, **layers** that add
to a base without editing it (`[layer]` header, `fits`), a theme map (`themes.toml`), a loader
that merges and checks both the merged set and each file, an authoring guide
(`docs/TOPOLOGY_RULES.md`) and `check`, `dry-run` and `draw` commands.

This step gives decor the same shape, then lets a person **see one room's decor**: pick a room
of a build in the page, see that room alone with its Props, POIs and Dressing, which recipe line
put each Prop there and what dropped and why, and re-decorate it in a second or two with another
seed, Decor level or layer, reading the rule files fresh so an edit shows without a restart.

`scripts/decor_room.py` (step 11) already decorates one RoomContext and writes a GLB of it
alone. The room view builds on it: a build already saves every room's RoomContext
(`<name>.rooms.json`, step 12).

This spec sits under the umbrella `zone-generator` and builds on step 11
(`zone-generator-room-decor/`) and step 12 (`zone-generator-world-sockets/`). "Req X.Y" means a
requirement of THIS spec unless it says otherwise.

**What changes.** New files under `rules/decor/layers/` and `rules/decor/themes.toml`; a new
request field naming extra decor layers; a new route and page view. **What doesn't:** every
build made without naming a layer is byte-identical to before (Req 6.1), including the theme
whose rules move into the worked example layer.

**Out of step 15:** new decor content beyond the worked example (layers are for later steps and
the user); editing rules from the page; corridors and Sites in the room view (rooms only; Sites
are a follow-up); the catalogue and tags (`tags.toml` stays as it is).

## Glossary

- **Base decor set**: `rules/decor/rooms.toml` with `sets.toml`, as today.
- **Decor layer**: a file `rules/decor/layers/<name>.toml` with a `[layer]` header (name,
  description) and any of the base's sections, merged onto the base at load time.
- **Decor theme map**: `rules/decor/themes.toml`, which layers each dungeon theme (and race)
  takes.
- **Room view**: the page's look at one room of a build, alone, with its decor laid out.

## Requirements

### Requirement 1 — Decor layers

**User story:** As someone writing decor rules, I want to write a self-contained file and drop
it in, as I would a topology layer, without editing the shared rules.

1. The loader SHALL read every `rules/decor/layers/*.toml`, each with a `[layer]` table holding
   `name` (matching the file name) and `description`, and SHALL accept in a layer any section the
   base takes: `kinds`, `types`, `zones`, `sites`, `groups`, `dressing`, `every`, `weights`,
   `once`.
2. Merging a layer onto the base SHALL add what is new; a recipe, Group, Dressing or weights
   entry the base (or an earlier layer) already has SHALL be refused, naming both files, unless
   the layer's entry says `mode = "add"` (its lines join the existing ones) or
   `mode = "replace"` (its lines stand instead).
3. Every layer file SHALL be checked on its own and the merged set checked as a whole, with
   every failure named by file, entry and field (`RuleSetError`), as the topology loader does.
4. Layers SHALL merge in a fixed order (theme map order, then request order), so a build is a
   function of its inputs.

### Requirement 2 — Choosing layers

1. `rules/decor/themes.toml` SHALL map a dungeon theme (and optionally a race) to the decor
   layers it takes; a theme not listed takes none.
2. A build request SHALL be able to name extra decor layers (`decor_layers`, a list of names)
   on top of the theme's, through the CLI (`--decor-layer`, repeatable), the server and the page
   (a **Decor rules** control listing the shipped layers, "From theme" by default).
3. `/api/controls` SHALL list the available layers with their descriptions, read from the
   folder, so a dropped-in file shows up without a code change.
4. An unknown layer name SHALL be refused with a 400 that names the known ones.
5. The sidecar's `decor` block SHALL record the layers the build used.

### Requirement 3 — The worked example and the guide

1. One theme's decor SHALL move from `rooms.toml` into a layer as the worked example
   (recommended: `tomb`, its weights and its ossuary and ritual-chamber recipes), mapped in
   `themes.toml`, with every tomb build byte-identical to before.
2. `docs/DECOR_RULES.md` SHALL be the authoring guide: the sections and fields, how lookup and
   Weights blend, how layers merge (`mode`), the worked example, the traps, and the commands.
3. `scripts/topology_rules.py check rules/decor` SHALL check every layer and each theme's merged
   set; `draw-decor` SHALL take `--layer` (repeatable) to show a merged set's draws.

### Requirement 4 — Re-decorating one room

1. A route SHALL re-decorate one room of a build from the build's saved RoomContexts, given the
   build, the room, and optionally a decor seed, a Decor level and decor layers, reading the
   rule files fresh on each call.
2. With the build's own seed, level and layers, it SHALL give the same Props as the build.
3. It SHALL answer with a GLB of the room alone (floor, walls as sampled, Features, POI markers,
   Props; as `scripts/decor_room.py` draws it) and a report: each Prop with its recipe line,
   step and arrangement; each POI with its purpose and Dressing; each drop with its line and
   reason.
4. It SHALL answer in under 3 s for a room of a 16-room dungeon on this machine, models cached.
5. A rule file that fails its check SHALL give a 400 naming the failures, not a server error.

### Requirement 5 — The room view in the page

**User story:** As someone polishing decor, I want to look at one room alone and see why each
thing is where it is, and try again quickly.

1. From a shown build, the user SHALL be able to open a room in the room view: from the side
   panel (a room list) and from the map dialog (clicking a room).
2. The room view SHALL show the room alone with an orbit camera framed on it, the Props drawn,
   POIs marked, and labels on request.
3. Beside it, a list SHALL group the Props by recipe line (e.g. `types.barracks props[1]`: 3
   beds, bunks), list each POI with its Dressing, and list the drops with their reasons;
   hovering a list entry SHALL highlight its Props in 3D, and hovering a Prop SHALL highlight
   its entry.
4. Controls in the room view SHALL re-decorate the room: **reroll** (a fresh decor seed),
   **Decor** level, **Decor rules** (layers), and **re-read rules** (same seed, rules read
   fresh); each answers within Req 4.4's time.
5. Closing the room view SHALL return to the zone as it was (camera and overlays).

### Requirement 6 — Nothing else changes

1. Every build that names no layer SHALL be byte-identical to before (all `.eqg` goldens, room
   and Site decor goldens, Zone_Spec hashes).
2. `cd web; npx vite build` SHALL succeed and the full Python suite stay green; the suite's time
   SHALL stay within its targets (fast < 8 min, full < 25 min).
