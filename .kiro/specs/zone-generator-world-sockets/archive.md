# Archive — zone-generator-world-sockets

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Answered by the user on 2026-11-12, one prompt per question.

1. **A dungeon Socket fixes the hill, not the exact Mouth** (recommended). The Attach stage
   picks the Mouth inside the `hillside` Socket after the rooms are laid out, as
   `plan_entrance` does today. Outdoor-dungeon bytes are kept.
2. **Site Sockets are an area** (recommended). One `ground` Socket; the Sites stage picks
   centres as now. Point Sockets stay a follow-up.
3. **Door Sockets: the kind is reserved, none is made** (recommended).
4. **Stage seeds are `seed` (World), `rooms_seed` (rooms and Sites), `decor_seed` (Props)**,
   each defaulting to `seed` (recommended). Trees stay on the World seed.
5. **A gate failure rerolls only the failing stage, in this step** (NOT the recommendation;
   the user chose it). Task 19 (Req 9). The rules the cards are cut to:
   - It applies only where the retry loop runs today: a gated zone type with a random seed.
     A pinned `seed` still fails as it does now (pinned seeds are never swapped), and so do
     a pinned `rooms_seed` or `decor_seed`.
   - The pipeline names the stage at fault from what the gate already reports: if the build
     passes with its Props left out, the fault is Decor and only `decor_seed` is redrawn; if
     it fails with no Props and the failing rooms or corridors lie inside an Attachment, the
     fault is the rooms and `rooms_seed` is redrawn (decor follows, since it is a later
     stage); otherwise, or when the stage can't be named, a fresh `seed` is drawn for
     everything, as today.
   - The World is kept across stage rerolls. After two stage rerolls on one World the next
     retry draws a fresh `seed`. All of this stays inside today's attempt cap and timeout.
   - Each rejected attempt's JSONL line names the stage blamed and the seeds it used.
6. **Hand-offs are written into each build directory only** (recommended): not page downloads,
   never read back by the server; `scripts/stage.py` reads them.
7. **Corridor RoomContexts: yes, as one late task** (recommended). Task 14 stays; Decor-on
   goldens, the room corpus and the P12 bands are recaptured once.
8. **Suite targets: the fast suite under 5 minutes, the full suite under 25** (recommended),
   every first-try and band check kept. Task 1 may revise them with the user's word.
   **Revised 2026-11-13 by the user: the fast suite under 8 minutes** (full suite still under
   25). Task 1 measured 16 min fast / 42 min full idle; four unmarked tests of 5-6 min each
   set a floor near 6 min, so they stay in the fast suite.

Added after the questions:

9. **An outdoor dungeon reads one landscape, fixed in step 12** (the user, 2026-11-13). Task 3
   found its spec takes the Spawn, regions and water from the requested Landform's landscape
   and everything else from the placed one (29 of seeds 0-39 differ). Task 20 makes all of it
   the placed one; every affected outdoor dungeon changes once.

## Follow-ups

Carried in from step 11 (`zone-generator-room-decor/archive.md` "Follow-ups") because they
sit on the stage hand-offs this step builds:

- **Corridor lights**: placement lights `source = "corridor"` contexts, but `room_context`
  builds none. Task 14, if design question 7 is answered yes; otherwise it stays here.
- **Reroll a room's contents while keeping its layout** (step 9): the decor seed covers
  Props, and this step's `rooms_seed` rerolls the whole layout; a seed for step 9's Structure
  and Clutter Features alone (the Attach stage split into layout and contents) stays open.
- **Doorway gates as doors** at room openings (M6, with the EQEmu `doors` records): related to
  the reserved `door` Socket kind (design question 3), not built here.

Carried in from step 10 (`zone-generator-wilderness-pois/archive.md` "Follow-ups"), because
point Site Sockets (design question 2) are where they would be fixed:

- **Sites spread at random** where stock plains cluster them.
- **Outdoor dungeons get Sites on only some seeds**: their open ground is small (about
  0.8e6 u²).

Found while working this step:

- **Stair and Bridge corridors get no decor** (task 14 left them out rather than read stair
  treads and bridge decks as the gate does).
- **City decor sits near its band tops** after task 14's retune: furniture .33 of a .34 top,
  light .43 of .45, container .14 of .15, and the rules' expected furniture .359 of a .36 cap.
  A small recipe change can tip one over.
- **`outdoor_dungeon.keep_clear_shapes` duplicates `stages.entrance_keep_clear`** (task 5; a
  test pins them equal). Only tests call the first now: delegate or delete it.
- **`build_outdoor_dungeon_ter`, `tunnel_doors` and `sidecar_block` still call
  `landscape_for`** instead of reading the World (tasks 4 and 6).
- ~~A build whose spec `world_of` can't remake now fails~~ (task 6). Retired by task 20:
  `world_of` reads the spec's own Landform, with no cross-check.

- **The page's Socket markers infer the map's world-to-pixel mapping** from the drawn room
  labels (`web/src/sockets.ts`, task 9), since the map SVG doesn't record it. A change to how
  `generators/mapview.py` draws labels would quietly drop the markers (a console warning is
  all). Sturdier: have `mapview.py` record the mapping on the SVG, or draw the Sockets itself.

Out of this step, named so they aren't lost:

- An exact Mouth Socket chosen by the World, and more than one dungeon in a World (design
  question 1).
- M4's partial rebuild (rebuilding only the changed stage's output); step 12 rerolls only
  the failing stage's seed on a gate failure (decision 5) but still builds the whole zone.
- Multi-zone worlds and zone lines between zones; the M6 SQL export.
