# Requirements Document

> **STATUS: roadmap step 13, ready.** Drafted 2026-11-14 at master `2448243`; the design's
> open questions were decided the same day on their recommendations (`archive.md`
> "Decisions"). Task index: `tasks.md` (card format).

## Introduction

Roadmap step 13: **point Site Sockets.** Step 12 made the World offer Sockets and the Attach
stage build on them, but Sites attach to an area: one `ground` Socket, on which the Sites
stage picks each centre itself, at random among scored spots (world-sockets decision 2,
"Point Sockets stay a follow-up"). Two defects from step 10 were left for this step
(`zone-generator-wilderness-pois/archive.md` "Follow-ups", carried by step 12):

- **Sites spread at random where stock plains cluster them.** Clark–Evans R pooled 1.45 over
  40 Normal builds (wilderness-pois task 11): inside the all-zone stock band 0.64–1.64, above
  the plains' own 0.50–0.95. The recipes' `spacing` (200–400 u between any two Sites) is part
  of why: stock plains put 33–65 % of their Sites within 300 u of another (design finding 1).
- **Outdoor dungeons get Sites on only some seeds**: 8 of 39 at Normal, 10 at Dense (design
  finding 3). Their open ground is about 0.82e6 u², the Host_Hill's disc keeps Sites off 70 %
  of it, and what is left is mostly flank too steep for any recipe.

This step makes the World offer **point** Site Sockets, chosen from the terrain and the stock
pattern, in groups as stock plains have them; the Sites stage attaches one Site to a point.
The `ground` Socket stays: it still holds the Spawn and the Kept_Clear shapes earlier
Attachments add.

This spec sits under the umbrella `zone-generator` (`.kiro/specs/zone-generator/`) and builds
on step 12 (`zone-generator-world-sockets/`). "Req X.Y" means a requirement of THIS spec
unless it says "umbrella", "step 10" or "step 12".

**What changes.** Every wilderness and outdoor-dungeon build with Sites (`sparse`, `normal`,
`dense`) changes: where its Sites stand and which kinds they are, and the trees near them.
Their `.eqg` goldens, the Site and Site-decor goldens, the World corpus and the room corpus's
Site recordings are recaptured deliberately, named in the commits and in `archive.md`
(Req 7.2).

**What doesn't.** Dungeon and city builds; every build with Sites `none` (step 9's bytes);
every Zone_Spec JSON (the World and the Sites are not in the spec); trees with Sites `none`;
the hillside Attachment's rooms and Entrance.

**Out of step 13:** new biomes (only plains has Site rules; stock's other biome groups are
measured and recorded, not built); roads between Sites; flattening ground under a Site (step
10 decision 1 stands); door Sockets; M4's partial rebuild; blaming a Site's gate failure on
the Sites stage (design question 8).

## Glossary

- **Point Socket**: a Socket of kind `site`: one point where a Site may stand, with how much
  free ground it has at each slope a recipe allows, and the Group it belongs to.
- **Group**: point Sockets the World places together, as stock's Sites near each other are:
  a hamlet of one to a few Sites within the Group gap of each other.
- **Group gap**: 300 u. Stock plains Sites this close are one Group; the grouping doesn't
  change between 300 and 400 u (design finding 1).
- **Free radius**: at a point and a slope limit, the radius of the largest disc round the
  point whose ground is all eligible at that slope: what a recipe's ground and margin need.
- **Clustering target**: the stock band a biome's built Sites must measure inside: Clark–Evans
  R (as `tests/test_site_bands.clark_evans` computes it) and the pooled nearest-Site spacing
  p10, per biome where stock supports it.
- **Kept_Clear, Site, Site_Clear, Spawn, Apron, Tunnel, Host_Hill, Socket, World,
  Attachment, Stage seed, World corpus, room corpus**: as steps 5, 10 and 12.

## Requirements

### Requirement 1: The point Socket

**User Story:** As the project owner, I want the World to say where Sites may stand, so that
the Sites stage builds a Site on a point instead of choosing ground itself.

1. A point Socket SHALL be a `Socket` of kind `site`, accepting `site`, at a point `(x, y, z)`
   (`z` the World's ground there), with its Group, its rank in the World's order, and its Free
   radius at each slope limit a Site recipe uses, in the Socket's `ground`.
2. The World's JSON form SHALL become version 2; a version 1 World file SHALL be refused on
   read, naming the file and both versions (step 12 Req 5.3).
3. Every number a point Socket carries SHALL be written exactly, as step 12's Sockets are.

### Requirement 2: The World offers point Sockets

**User Story:** As the project owner, I want the World to choose Site spots from the terrain
and the stock pattern, so that Sites cluster as stock's do and stand where they fit.

1. A wilderness or outdoor-dungeon World SHALL offer point Sockets, chosen from the World's
   own inputs and the biome's clustering rules alone; the Sites control, the Inhabitants
   control, the plan's room fields and `rooms_seed` SHALL NOT reach them (step 12 Req 2.1).
2. Points SHALL stand only on ground a Site could use: playable, reached from Spawn, dry,
   outside the trees' Kept_Clear (Spawn clearing, zoneline approaches, shores), with a Free
   radius of at least the smallest recipe's ground and margin at that recipe's slope.
3. Points SHALL come in Groups: a Group's sizes drawn from the biome's stock distribution, its
   points within the Group gap of another of its points and far enough apart that each one's
   Site ground and margin keep a clear width between them; Groups apart by at least the
   biome's Group spacing.
4. A World SHALL offer at least enough points for the Dense control's largest target, with
   spares, so that points the Attach stage drops (Requirement 3.3) don't starve it.
5. The same World inputs SHALL give the same points, equal as JSON text.
6. The World stage SHALL stay fast: points add at most 0.1 s to a World (median over the
   timing seeds, `scripts/stage_timings.py`).
7. The clustering rules SHALL be checked data under `rules/sites/` (`biomes.toml`), per biome;
   only plains is filled in this step.

### Requirement 3: Sites attach to point Sockets

**User Story:** As a user, I want each Site built on a spot the World offered, so that Sites
sit in hamlets on good ground and a reroll moves them among those spots.

1. The Sites stage SHALL attach each Site to one point Socket and record its Socket id in the
   Site's data.
2. A Site's kind SHALL be drawn, by the biome's and Inhabitant's weights times the recipe's
   likes at the point, from the kinds whose recipe ground and margin fit the point's Free radius
   at the recipe's slope and keep a clear width from every earlier Site's ground; a point no
   kind fits is passed over, and a Site with no point left is dropped and recorded (step 10
   Req 4.3).
3. A point whose Free radius disc meets a Kept_Clear shape on the `ground` Socket (added by an
   earlier Attachment) SHALL be passed over.
4. The Sites control SHALL still set how many Sites are tried (step 10's target); the Sites
   stage SHALL take points Group by Group, each next Group drawn from `rooms_seed` with a
   chance in proportion to its size, so a reroll of the rooms moves Sites among the World's
   Groups (design question 2).
5. The recipes' own `spacing` SHALL be retired: Groups set the spacing (design question 5).
6. Everything a Site does inside its ground (arrangement, Site_Clear, POIs, drops) SHALL be
   step 10's.
7. A Site's approach SHALL keep off every earlier Site's ground, so Sites in one Group don't
   block each other's way in.
8. With Sites `none`, nothing SHALL be attached and the build SHALL be step 9's bytes.

### Requirement 4: Clustering as stock

**User Story:** As the project owner, I want built Sites to cluster as stock plains do, so
that a zone reads as places someone chose, not a scatter.

1. Over the band seeds (1000–1039) at Normal, built wilderness zones SHALL measure inside the
   plains clustering target (design finding 1): Clark–Evans R pooled 0.50–0.95; the share of
   Sites with another Site within 300 u, pooled, 33–65 %; and pooled spacing p10 108–191 u.
2. At Dense, the median zone's R SHALL be inside 0.50–0.95.
3. Step 10's other bands SHALL still hold at Normal: Sites per 1e6 u² (0.3–0.5), Structures
   per Site (zone p50 1–3, p90 1.8–5.6).
4. A placement-only check of Requirement 4.1, on Worlds alone (no TER, no build, no gate),
   SHALL run in the fast suite.

### Requirement 5: Outdoor dungeons get Sites

**User Story:** As a user, I want an outdoor dungeon at Normal to have a Site near it, as the
wilderness does, rather than on one seed in five.

1. The outdoor dungeon's Kept_Clear for Sites SHALL be its own rooms and corridors (grown by a
   margin), its Tunnel and its Apron, not the Host_Hill's whole disc (design question 3).
2. At Normal and Dense an outdoor dungeon SHALL try at least one Site; Sparse keeps step 10's
   draw (design question 4).
3. Over seeds 0–39, an outdoor dungeon at Normal SHALL get a Site on at least 35 of the seeds
   that plan (today 8 of 39).
4. No Site, Structure or Site_Clear SHALL stand over a room or corridor of the dungeon, on its
   Tunnel, or on its Apron.

### Requirement 6: Seeds, hand-offs and rerolls

1. Points SHALL be drawn from the World's seed, on their own salted stream; the Sites'
   order of Groups, Inhabitants, kinds and arrangement from `rooms_seed` (step 12 decision 4).
2. A build with a new `rooms_seed` and the same seed SHALL keep the World file text, points
   included (step 12 Req 4.2).
3. The Attachments file SHALL become version 2 (each Site names its point Socket); a version 1
   file SHALL be refused on read, named.
4. The sidecar's `sockets` block SHALL list the point Sockets and, for each, the Site attached
   (its kind) or none; no existing key changes meaning.
5. `scripts/stage.py` SHALL run the `world` and `attach` stages on version 2 files, and the
   `world` GLB SHALL mark the point Sockets.

### Requirement 7: Bytes

1. Dungeon and city goldens, the Sites `none` goldens (`test_site_builds.py` STEP9), and every
   Zone_Spec hash SHALL be unchanged.
2. The builds named under "What changes" in the introduction SHALL be recaptured in the commit
   that changes them, with the old and new Site counts in its body: wilderness builds once (the
   Sites move to points), outdoor dungeons twice (that, then their Kept_Clear and count).

### Requirement 8: The gate

1. The zone gate's first-try rate SHALL be no worse than step 12's: wilderness seeds
   1000–1039 at Normal and Dense, outdoor dungeons seeds 0–39 at Normal and Dense.
2. Sites SHALL still cost at most 5 s on top of Sites `none` (step 10 Req 9.4).

### Requirement 9: The map

1. The web map SHALL mark every point Socket, the ones a Site attached to apart from the
   unused ones, with a tooltip naming its Group and what attached.
2. The map SVG SHALL record its world-to-pixel frame, so the page places Sockets from it rather
   than inferring it from room labels (step 12 follow-up, `web/src/sockets.ts`).

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it, a step in
   `docs/ACCEPTANCE.md` "Step 13 — Point Site Sockets".
2. The fast and full suites are green inside step 12's targets (fast under 8 min, full under
   25, idle); the frontend builds.
3. The user signs off a first look and an acceptance pass: wilderness Sites read as hamlets,
   outdoor dungeons have a Site, Sites stay off the dungeon, and the map shows the points.
