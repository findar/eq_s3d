# Writing decor rules

This guide is for anyone writing decor rules: a person editing TOML by hand, or
a model writing a layer from a prompt. It covers what the rules do, the file
format field by field, how a room finds its recipe and how the Weights blend,
how decor layers merge onto the shared file, the tomb layer as a worked
example, how to try a layer on a build, the check and draw loop, and the traps.

The designs are `.kiro/specs/zone-generator-room-decor/design.md` (the recipes,
step 11) and `.kiro/specs/zone-generator-decor-rules/design.md` (layers, step 15).
The code is in `generators/decor/`: `rules.py` loads and checks the files,
`placement.py` places Props from them, and `catalogue.py` holds the model Tags.
Topology rules have their own guide, `docs/TOPOLOGY_RULES.md`.

## What decor rules do

Decor furnishes a built zone's rooms, corridors and Sites with stock models
(Props). Each room is placed on its own from its RoomContext (its floor, walls,
Features and POIs), so Props never change the geometry. For each room:

1. Its **Dressing** goes first: lines round each POI, by the POI's purpose (a
   throne behind the boss, candles flanking the altar).
2. Then its **recipe**: the lines of its room type's recipe, else its kind's,
   else its zone type's, else the default (see "Lookup").
3. Then the **`every` lines**, which every room takes after its own: the wall
   lights and the mess.

A line asks for Props by **Tag**: a catalogue kind (`torch`, or a list of
kinds, best first) or a **Group** of kinds placed together. Only models with
`use = "yes"` in the catalogue fill it. How many a line places is its `count`,
times its Category's **Weight** for this room, times its **Scale**, times the
**Decor control** (none / sparse / normal / dense); `chance` says how likely
the line is at all. `bare` is the chance a room takes only its Dressing.

A **decor layer** is a small file that adds to the shared rules (or extends or
replaces an entry) for one theme, one race or one build, without editing
`rooms.toml`. `themes.toml` says which themes and races take which layers.

## Files

All under `rules/decor/`:

| File | What it holds |
|---|---|
| `rooms.toml` | the base: recipes, Groups, Dressing, Weights, `moves`, `once` |
| `sets.toml` | which culture's models (Sets) a room takes, by race, theme and zone type |
| `tags.toml`, `catalogue.json` | every stock model and its Tags (kind, Category, Mount, Set, `use`) |
| `themes.toml` | which decor layers each dungeon theme and race takes |
| `layers/<name>.toml` | a decor layer; `layers/README.md` is the short form of this guide |

Scales (`by`) are `rules/rooms/scales.toml`'s: `finish`, `structure`, `clutter`.

## The format, field by field

### The sections of `rooms.toml`

| Section | Required | What it is |
|---|---|---|
| `[default]` | yes | the recipe of a room with no room type, kind or zone recipe |
| `[every]` | yes | lines every room takes after its own recipe (not Sites) |
| `[kinds.<room kind>]` | | a recipe by room kind (`entrance`, `chamber`, `passage`, `hub`, `lair`, `hall`, `deep`) |
| `[types.<room type>]` | | a recipe by room type (`ossuary`, `barracks`, ...: `generators/semantics.py` ROOM_TYPES) |
| `[zones.<zone type>]` | | a recipe for a zone type's rooms with neither type nor kind (a city's) |
| `[sites.<Site kind>]` | | a Site kind's recipe (camp, hut, ...); a Site takes no `every` lines |
| `[groups.<name>]` | | Props placed together, whole or not at all |
| `[dressing.<POI purpose>]` | yes (`boss`, `treasure`, `altar`, `guard`) | lines round a POI |
| `[weights.*]` | yes (`default`, `controls`) | the Weights by Layer, below |
| `moves` | | Category -> the Scale that moves its lines: `{ debris = "clutter", furniture = "structure" }` |
| `once` | | kinds a room holds at most once: `["anvil", "forge"]` |

A recipe, `every` and a Dressing entry are each a table with one key, `props`,
a list of lines. An empty list (`props = []`) is a recipe that adds nothing.

### A line

```toml
{ kind = ["torch", "lantern"], at = "on_wall", count = [1, 2], chance = 0.9, by = "finish", from = 3 }
```

| Field | Required | Values |
|---|---|---|
| `kind` | one of `kind`, `group` | a catalogue kind, or a list of them, best first |
| `group` | one of `kind`, `group` | a Group name; a Group stands on the floor |
| `at` | yes | room lines: `on_wall`, `ceiling` (their own Mounts); `along_wall`, `corners`, `centre`, `far_end`, `scatter`, `rows`, `by_door`, `on_dais` (floor). Dressing: `beside`, `behind`, `flank`, `round` (floor), `wall` |
| `count` | | a number or `[low, high]` (default 1), at most 12 |
| `chance` | | 0 to 1 (default 1) |
| `by` | | `finish`, `structure` or `clutter`; left out, the line takes its Category's from `moves` |
| `from` | | 0 to 10: the line is there only from this value of its Scale up |

The **Mount** follows from `at`: `on_wall` and `wall` ask for wall models,
`ceiling` for ceiling ones, a Group's `stack` for one that stands on another,
the rest for floor models. The **Category** is the first kind's (or the Group's
anchor's): light, container, furniture, hanging, structure, debris, plant or
other. A light line `on_wall` or at `corners` is placed as one symmetric set.

### A Group

```toml
[groups.table_set]
members = [ { kind = ["table", "desk"], at = "anchor" },
            { kind = ["chair", "stool", "bench"], at = "round", count = [1, 3] },
            { kind = ["candle", "tableware", "book"], at = "stack", count = [0, 2] } ]
```

The first member is the `anchor`; the rest stand `round` it, in a `row` with
it, `beside` it, or on it (`stack`, a raised Mount). A member has `kind`, `at`
and an optional `count`. The Group is placed whole or not at all.

### Weights

```toml
[weights.default]                       # every Category and bare: every room starts here
light = 1
...
bare = 0.26

[weights.controls.sparse]               # the Decor control, applied on top of the blend
light = 0.6

[weights.zone_types.city]               # Layers, least specific first:
light = { value = 1.1, override = true }
[weights.races.goblin]                  #   zone_types, races, themes, kinds, types
light = 1.6
```

Each entry names some of the Categories (and `bare`, not in a control). A value
is a number of 0 or more (`bare` at most 1), or `{ value = 3, override = true }`.

## Lookup and how the Weights blend

**Which recipe.** A room takes its room type's recipe (`types.X`), else its
kind's (`kinds.X`), else its zone type's (`zones.X`), else `default`; then
`every`. A Site takes `sites.<kind>` alone. A room type without its own recipe
falls back silently, so check which one a type takes (`check rules/decor` says
how many types have their own, and `draw-decor` lists "takes ..." per type).

**The Weights.** A room's Layers are the default, then its zone type's, race's,
theme's, room kind's and room type's entries, where they exist. For each
Category the weight is the **geometric mean of the Layers that name it**, the
blend step 9's Scales use. So a value stands against the default's 1: write the
number you would want alone, squared. A theme's `debris = 2.5` gives a plain
room 1.58; a vault in a tomb blends the default's 1, the tomb's 2.5 and the
vault's 0.2 to 0.79. An `override = true` value replaces every less specific
Layer (a city writes its own, not a blend with the dungeon's). The Decor control
multiplies the result; `bare` is not moved by it.

**The Scales.** A line's Scale (its `by`, else `moves`) at 5 leaves the line as
written, 0 removes it, 10 doubles it, and under `from` the line isn't there.

## Layers and `mode`

A layer is `rules/decor/layers/<name>.toml`: a `[layer]` header and any of the
base's sections but `default` and `moves`.

```toml
[layer]
name        = "bones"                    # the file's name
description = "Bones in the barracks, darker deep rooms"

[groups.bone_heap]                       # new: added
members = [ { kind = "skull", at = "anchor" }, { kind = "bones", at = "round", count = [1, 3] } ]

[types.barracks]                         # already in rooms.toml: says what to do with it
mode  = "add"
props = [ { group = "bone_heap", at = "scatter", chance = 0.5 } ]

[weights.kinds.deep]                     # new Weights entry
light = 0.5
```

**Merging.** For each entry (a recipe, `every`, a Group, a Dressing, a Weights
entry):

- one the base and earlier layers don't have is **added**;
- one already there is **refused, naming both files**, unless it says `mode`:
  - `mode = "add"`: its lines (a Group's members) join the existing ones, after
    them. On a Weights entry its Categories join the entry's, and a Category the
    entry already names is refused;
  - `mode = "replace"`: it stands instead of the existing entry, whole;
- a `mode` on a new entry is allowed; the entry is simply added.

`once` kinds join the base's. Layers merge in order: a build takes its theme's
layers, then its race's (both from `themes.toml`), then the ones the request
names, each once, where it first stands. Each layer is checked on its own
(failures name its file), then the merged set as a whole (failures name
`rooms.toml + bones.toml`), so a layer that is sound alone can still break the
set. A line a layer wrote keeps its file in reports: the sidecar's Props and
drops name `bones.toml types.barracks props[0]`.

**The theme map.** `themes.toml`:

```toml
tomb = { layers = ["tomb"] }

[races]
goblin = { layers = ["goblin_clutter"] }
```

Theme names are the dungeon themes; race names the dungeon races and the Site
Inhabitants. Every layer named must be a file in `layers/`. A theme or race not
listed takes no layer.

## Worked example: the `tomb` layer

[`rules/decor/layers/tomb.toml`](../rules/decor/layers/tomb.toml) is the tomb
theme's decor, moved out of `rooms.toml` in step 15 and mapped
`tomb = { layers = ["tomb"] }`:

```toml
[layer]
name        = "tomb"
description = "Befallen's look: bones and debris, hanging chains, almost no light"

[weights.themes.tomb]
light = 0.1
furniture = 0.4
debris = 2.5
hanging = 2
```

**What moved, and why only this.** A layer the theme map gives to tombs reaches
tomb builds alone, so only what tomb rooms *alone* reach may move. A tomb's
rooms take entry_hall, passage, ossuary, ritual_chamber, collapsed_gallery and
vault (`generators/semantics.py`). `coverage` over every theme's room types
shows each of those recipes reached by another theme as well:

| Recipe | Themes whose rooms reach it |
|---|---|
| `types.ossuary` | tomb, temple, corrupted_sanctum, sunken_ruin, ice_keep |
| `types.ritual_chamber` | tomb, temple, sunken_ruin |
| `types.vault` | tomb, mine_delve, lava_forge |
| `types.collapsed_gallery` | tomb, warren, mine_delve, lava_forge, ice_keep |
| `types.entry_hall`, `types.passage` | most themes |

Moving the ossuary recipe would strip a temple's ossuary of its bones. So the
recipes stay in the base and the layer holds the tomb's Weights: a tomb room's
light falls to 0.32 of a plain room's, its debris rises to 1.58.

**How it was proved the same.** Base + tomb loads the same `DecorRules` as the
base with the tomb's table pasted back in (`tests/test_decor_layers.py`), so a
tomb room gets the same recipes and Weights as before; and a decorated Theme
Tomb build gives the same `.eqg` bytes as before the move (the `TOMB` golden in
`tests/test_decor_builds.py`, captured first). The sidecar's `decor` block now
also lists `layers: ["tomb"]`.

**Taking it further.** To give a tomb's ossuaries something a temple's lack,
extend the base recipe from the layer rather than moving it:

```toml
[types.ossuary]
mode  = "add"
props = [ { kind = ["corpse", "skull"], at = "scatter", count = [1, 2], chance = 0.5 } ]
```

That changes tomb builds' bytes (on purpose), so recapture the `TOMB` golden.

## Trying a layer on a build

A layer the theme map doesn't give a build can still be tried on it, on top of
the theme's:

- **Command line**: `python main.py ... --decor-layer bones` (repeat for more,
  merged in order). An unknown name exits 2 naming the known ones.
- **The page**: the Decor rules control (step 15 task 5) lists every file in
  `layers/` with its description (`/api/controls`' `decor_layers`).
- **The API**: `controls.decor_layers: ["bones"]` in a generate request; an
  unknown name is a 400.

Only Decor reads the layers: the geometry, rooms and Sites are the same with or
without them, and the sidecar's `decor.layers` names what a build took. The
builder caches one merged set per tuple of layers, per process: restart the
server after editing a layer file.

## The loop: check, draw

```bash
python scripts/topology_rules.py check rules/decor            # the base, each layer, each mapped theme
python scripts/topology_rules.py check rules/decor --strict   # ... failing on unmet Tags too
python scripts/topology_rules.py draw-decor                   # output/rules/decor.html
python scripts/topology_rules.py draw-decor --layer tomb      # ... with layers merged (repeatable)
```

1. **check** loads the base, then each file in `layers/` merged onto it alone,
   then each theme and race in `themes.toml` with its layers. It prints `ok`
   or `FAIL` per step (a layer's line lists its entries), the lines no
   `use = "yes"` model meets as `unmet` (a failure only with `--strict`; at
   build time they drop), and exits 1 if anything failed:

   ```
   ok    decor/: decor, 24 type, 7 kind and 6 Site recipes, 7 groups, ...
   ok    decor/layers/tomb.toml: decor layer, 1 entry: weights.themes.tomb
   ok    decor/themes.toml: decor theme map, 1 theme(s), 0 race(s)
   ok    theme tomb (rooms.toml + tomb.toml): merged
   ```

2. **draw-decor** writes `decor.html` (`--out` to put it elsewhere): Props per
   room and Category shares by zone type, race and theme (a mapped theme drawn
   with its layers, "theme tomb (+ tomb)"), by recipe, a schematic plan of each
   recipe, the Dressing, the Sets, and the unmet lines. `--layer` merges layers
   onto the whole page. Open it in a browser; `output/` is gitignored.

### What a check error looks like

Every failure names the file, the entry and the field:

```
crypt.toml › types.ossuary › mode: found nothing, expected mode = "add" (its props join the
    existing ones) or "replace" (they stand instead): types.ossuary is already in rooms.toml
crypt.toml › weights.themes.temple › light: found 0.5, expected a Category not already in
    weights.themes.temple (rooms.toml has it); mode = "replace" stands for the whole entry
nope.toml › layer › name: found "nope", expected a decor layer in decor/layers/: one of tomb
```

## Traps

- **A recipe other themes reach is not the theme's to move.** Room types are
  shared between themes (an ossuary is in five). Check with `coverage` across
  every theme before moving a recipe into a theme's layer; extend it with
  `mode = "add"` instead.
- **Write Weights squared.** The blend is a geometric mean with the default's
  1: `debris = 2` gives 1.41, not 2. Use `override = true` only when the entry
  must stand alone (a city's), since it silences the race and theme too.
- **`mode = "replace"` replaces the whole entry.** A Weights entry replaced with
  `light = 0.3` loses its other Categories; a recipe replaced loses every line.
- **`mode = "add"` on Weights refuses a Category already there.** Use
  `"replace"` and write the whole entry when you mean to change one.
- **The merged set is checked as a whole.** A layer can be fine alone and still
  break the set: replacing `weights.default` without every Category fails as
  `rooms.toml + <layer>.toml`.
- **Unmet lines drop quietly at build time.** A kind with no `use = "yes"` model
  at the line's Mount places nothing; `check` lists them, `--strict` fails.
- **The build caches the rules per process.** Edit a layer, then restart the
  server (the room view, step 15 task 4, reads the files fresh).
- **Scripts that load the base alone don't see a theme's layers.**
  `load_decor()` with no `layers` is the base; anything decorating a tomb room
  should load `layers_for(theme, race)` the way the builder does.

## Writing a layer (checklist for a person or a model)

1. Name the file for what it is (`layers/<name>.toml`) and give `[layer]` its
   `name` (the file's) and a one-line `description` (the page shows it).
2. Decide who takes it: a theme or race in `themes.toml`, or only builds that
   name it.
3. For each entry, ask whether the base already has it. New: just write it.
   There: `mode = "add"` to extend, `"replace"` to stand instead.
4. Use kinds the catalogue has `use = "yes"` models for at the line's Mount.
5. Run `check rules/decor`, then `draw-decor --layer <name>` and compare the
   Props per room and the shares with the base page.
6. Try it on a build (`--decor-layer <name>`) and look at the rooms in the
   viewer. If a mapped layer changes shipped builds, recapture their goldens.
