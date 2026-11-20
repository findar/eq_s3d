# Design — zone-generator-cave (roadmap step 21)

Written at master `a377d54`. Verify against the code before working. The umbrella design's
"Semantics" section (the `cave` archetype table) and "Cave keywords" are the starting point,
amended by `requirements.md` A1–A6.

## Where a Purpose lives today

A Purpose is spread over these tables; `cave` needs an entry in each:

| Place | What | Task |
|---|---|---|
| `generators/semantics.py` `ROOM_TYPES` | the four new Room_Types | 1 |
| `generators/semantics.py` `ARCHETYPES` | entrance / hub / climax / arc | 1 |
| `generators/semantics.py` `_THEME_KIND_TYPES` | graph-layout kinds → Room_Types | 1 |
| `generators/semantics.py` `_THEME_PALETTES` | floor / wall colour and description | 1 |
| `ai/schema.py` `VALID_DUNGEON_THEMES` | the vocabulary (planner, Server, CLI, LLM enum, rule validators) | 1 |
| `rules/rooms/scales.toml` `[themes.cave]` | finish / structure / clutter | 2 |
| `rules/rooms/layouts.toml` `[types.*]` | recipes for the new Room_Types | 2 |
| `rules/topology/themes.toml` | the rule set (`warren` base is the cave-like one) | 2 |
| `styles/texture_recipes.json` | procedural wall / floor textures | 2 |
| `rules/decor/themes.toml`, `rules/decor/layers/cave.toml` | decor layer | 3 |
| `ai/expand.py` / `generators/layout.py` | `style_profile = "cave"`, `floor_area` from it | 4 |
| `ai/rule_planner.py` `_ARCHETYPE_WORDS` | cave words | 5 |
| `generators/districts.py` compatibility pairs | neighbours for `cave` | 5 |
| `web/index.html` `#dungeon-theme` | "Cave" option | 5 |

Task 1 adds the name to `VALID_DUNGEON_THEMES` and `ARCHETYPES` at once. Rule validators that
list the vocabulary (`room_scales`, `topology/ruleset`, `decor/rules`, `decor/catalogue`) accept a
theme with no entry, but Room_Types are different: `room_layouts` needs a recipe in
`rules/rooms/layouts.toml` for every `ROOM_TYPES` name, so task 1 adds empty ones
(`features = []`) for the four new types and task 2 fills them.

## Room_Types (task 1)

From the umbrella table, sized like their nearest existing type:

| Type | Like | Shape | Light | Region |
|---|---|---|---|---|
| `cave_mouth` | `entry_hall` | footprint ≈ 1.2, ceiling ≈ 0.85 | `_COLD`, moderate | — |
| `cavern` | `summoning_hall` | footprint ≈ 1.35, ceiling ≈ 1.3 | `_COLD`, low | — |
| `crystal_grotto` | `inner_sanctum` | footprint ≈ 1.1, ceiling ≈ 1.3 | `_ARCANE`/cold mix, bright | — |
| `grotto` | `prison_cell` | footprint ≈ 0.75, ceiling ≈ 0.8 | `_COLD`, low | — |

Arc: `passage`, `grotto`, `flooded_gallery`, `sump`, `collapsed_gallery`, `warren`. Props and
encounter strings are suggestions only (Req 27). Keep `ROOM_TYPES` insertion order for the
existing entries; add the new ones at the end of their group, and confirm no code iterates
`ROOM_TYPES` in an rng-dependent way (A6).

## Rule files (tasks 2 and 3)

- **Finish:** `[themes.cave] finish = { peak = 1, spread = 2 }` like `warren`, structure low,
  clutter around 4. Compare with `[overlays.natural_cave]` (the outdoor dungeon with no theme),
  which already describes Blackburrow.
- **Topology:** `cave = { base = "warren" }` unless the warren set's kinds don't cover `cave`'s
  Room_Types; then `classic_eq`. Record which in the commit body.
- **Textures:** a `rock` / `cave` family wall and a damp-stone floor, by analogy with
  `ice_keep`'s entries (`{"theme": ..., "surface": ..., "family": ...}`).
- **Decor:** a `cave` layer in `rules/decor/layers/` (format: `layers/tomb.toml`, guide
  `docs/DECOR_RULES.md`): crystal models (`CRYSTAL*`, `CRYS*` from Runnyeye/Najena) in
  `crystal_grotto` and `cavern`, rock and mushroom models where the catalogue has them; nothing
  built (no furniture, banners, braziers).

## Style profile (task 4)

`plan_to_spec` (`ai/expand.py`) sets `spec.style_profile = STYLE_PROFILE[plan.zone_type]`
today, and `LayoutGenerator.__init__` loads the profile by zone type. Add a `profile` (or
`style_profile`) argument to `LayoutGenerator` defaulting to today's lookup, pass `"cave"` when
the zone's Purpose (or District 0's, when Districts are on) is `cave`, and set
`spec.style_profile` to match. Only `floor_area` (room scale) is read from the profile for the
layout; `styles/cave.json`'s mean is about 15% under `dungeon.json`'s. Any other zone passes
no profile, so its layout is unchanged (A6). `generators/layout.py` is a hotspot: keep the edit
to the constructor and the one call.

## Planner, page and Districts (task 5)

- `_ARCHETYPE_WORDS["cave"] = ["cave", "cavern", "caverns", "grotto", "underground", "tunnel",
  "tunnels", "stalactite", ...]`. The `dungeon` zone-type bucket keeps its cave words (A5).
- `tests/test_properties_layout.py::test_cave_words_mean_dungeon` (M0 property 19) still holds:
  the zone type stays `dungeon`. Its docstring's "never yields a cave theme" now means zone type,
  not Purpose; update the wording, not the assertion. The step 19 follow-up ("cave outdoor
  dungeon" read as an outdoor dungeon) is zone-type detection and out of scope.
- Districts' compatibility pairs (`generators/districts.py`): `cave` next to `warren`,
  `mine_delve`, `sunken_ruin`, `ice_keep`, `lava_forge`, `tomb`; contrasting (factional) with
  `fortress`, `temple`, `wizard_lair`. `cave` also needs a palette (it is in `_THEME_PALETTES`, so
  `PURPOSE_PALETTES` picks it up).
- Page: `<option value="cave">Cave</option>` in `#dungeon-theme`; the hygiene test's control
  lists if they enumerate options.

## Gate and bands (task 6)

`scripts/sweep_themed_navigability.py` gains `cave`; run it for both layouts, 2–30 rooms, each
verticality. `scripts/quality_sweep.py` (or a one-off script) draws ≥ 200 `cave` Draws per layout
and reports the fail share against today's bands. A failure is a real bug to fix at its root
(project rule), not a band to loosen; above ~5% fail share, a `cave` band row is added and
recorded as an `archive.md` decision.

## Bytes

Every task that touches generation runs the byte check in `requirements.md`'s glossary.
