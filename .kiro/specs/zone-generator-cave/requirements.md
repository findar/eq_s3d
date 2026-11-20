# Requirements Document

> **STATUS: roadmap step 21, DONE (closed 2026-11-20; first look skipped at the user's word).** Drafted 2026-11-19 at master `a377d54`. After step 20 the
> user said "Continue"; multi-zone worlds still wait on their design review, so the lead chose
> the last unbuilt piece of umbrella M3: the `cave` Purpose (umbrella Requirement 33, design
> "Semantics", "`cave` archetype"). The user confirms the choice at the first look (task 8).
> Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

Caves are not a zone type or a geometry pipeline (umbrella Introduction, Req 7.11): a cave is a
`dungeon` whose Purpose is `cave`. Today a prompt like "a dark cavern" plans as a dungeon with
the default Purpose (`fortress`), the M0 stopgap the umbrella design calls "Interim (M0 → M3)".
This step adds the `cave` Purpose: its room vocabulary, palette, light mood and regions, its room
scale from the measured `styles/cave.json`, its rule-file entries (finish, recipes, topology,
decor), the planner's cave words, the page's option, and Districts' compatibility table.

The organic look comes from what exists: the `rough` wall style (`rules/walls/rough.toml`,
measured on Blackburrow, Runnyeye, Crystal Caverns and others) is drawn by rooms whose finish is
0–3, so a `cave` Purpose with a low finish gets wandering walls and a moving ceiling on the Box
backend. The Natural_Style (umbrella Req 7, M5) stays a separate, later step.

## Amendments to the umbrella

- **A1 — The look is the `rough` wall style, not the Natural_Style.** The `cave` Purpose's
  finish scale peaks low so its rooms draw `rough` (and some `hewn`); no new geometry code. M5's
  Natural_Style remains its own step.
- **A2 — Room vocabulary as the umbrella design's table.** New Room_Types `cave_mouth`,
  `cavern`, `crystal_grotto`, `grotto`; the arc reuses `passage`, `flooded_gallery`, `sump`,
  `collapsed_gallery`, `warren`. Each is a `RoomType` the Box backend realises today.
- **A3 — Style profile `cave` sets room scale; bands are unchanged unless measured otherwise.**
  A single-District `cave` zone (or one whose District 0 is `cave`) gets
  `spec.style_profile = "cave"`, so `floor_area` comes from `styles/cave.json`. Quality bands stay
  keyed as step 20 left them (no Purpose in the key); the sweep of task 6 measures `cave`'s fail
  share and only above about 5% adds a `cave` row (recorded as a decision).
- **A4 — Districts learn `cave`.** `cave` joins the Purpose vocabulary and the compatibility
  table. A districted zone whose Purposes are drawn (none proposed) may come out differently for
  the same seed, because the vocabulary grew; no golden covers that.
- **A5 — Cave words choose the Purpose, not the zone type.** "cave", "cavern", "grotto",
  "underground", "tunnel" score for `cave` among the Purposes; "mine", "delve", "quarry" stay
  with `mine_delve`; zone-type detection (including the outdoor-dungeon phrases such as "cave in
  a hill") is unchanged.
- **A6 — Bytes.** Every zone built today (any other Purpose, or none) stays byte-identical.

## Glossary

- **Purpose**: a dungeon's content theme (`dungeon_theme` in the plan, `VALID_DUNGEON_THEMES`;
  `semantics.ARCHETYPES`). Shown as "Theme" on the page.
- **Finish**: the room scale (`rules/rooms/scales.toml`) that picks the wall style: 0–3 `rough`,
  4–6 `hewn`, 7–10 `built`.
- **Byte check**: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py
  tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.

## Requirements

### Requirement 1: The `cave` Purpose

1. `cave` is in `semantics.ARCHETYPES` and `ai.schema.VALID_DUNGEON_THEMES`, with entrance
   `cave_mouth`, hub `cavern`, climax `crystal_grotto` and an arc from A2.
2. The new Room_Types carry footprint, ceiling, sink, light and region as the umbrella design's
   table describes (`cave_mouth` wide and low; `cavern` large and tall; `crystal_grotto` tall
   with a cold/arcane glow; `grotto` small and low); `flooded_gallery` keeps its `water` region.
3. `cave` maps the graph layout's kinds (`kind_types`) to its Room_Types, none unmapped.
4. A palette (damp rock, wet stone, mineral) and a light mood (cool blue-grey, low intensity,
   brighter accent in crystal rooms) distinct from every other Purpose's.

### Requirement 2: Rule files

1. `rules/rooms/scales.toml` `[themes.cave]`: a finish peaking low enough that most rooms draw
   `rough` (A1), structure low, clutter moderate.
2. `rules/rooms/layouts.toml` recipes for the new Room_Types; `rules/topology/themes.toml` names
   `cave`'s rule set.
3. `styles/texture_recipes.json` procedural recipes for `cave`'s wall and floor.
4. `rules/decor/themes.toml` gives `cave` a decor layer (crystals in crystal rooms, rock and
   fungus, no built furniture), using models already in `rules/decor/catalogue.json`.
5. Every rule file still loads and validates (`tests/test_decor_rules.py`, the room-scale and
   topology checks).

### Requirement 3: Room scale

1. A `cave` zone's `spec.style_profile` is `cave` (A3) and its layout reads `floor_area` from
   that profile; every other zone's profile is unchanged.
2. A saved spec keeps its `style_profile` on load and rebuild.

### Requirement 4: Planner, page, CLI and Districts

1. The rule planner maps the cave words to Purpose `cave` (A5); a prompt naming another Purpose
   more strongly keeps it; zone-type detection is unchanged.
2. The LLM planner's Purpose enum includes `cave` (through `VALID_DUNGEON_THEMES`).
3. The page's Theme list (`#dungeon-theme`) offers "Cave"; the CLI's `--district-theme`
   accepts `cave` (the CLI has no single-Purpose flag; a prompt sets it).
4. Districts: `cave` in the compatibility table with sensible neighbours (A4); a pinned `cave`
   gives every District `cave` with the variant levels.

### Requirement 5: Navigable and in band

1. `cave` dungeons pass the traversability gate on both layouts, 2–30 rooms, each verticality.
2. Their quality fail share is measured over at least 200 Draws per layout (A3).

### Requirement 6: Bytes

The byte check passes with no golden recaptured (A6).
