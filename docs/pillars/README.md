# Pillars

The project's work organised by the outcome it serves rather than by the order it was done.
Each pillar has four files:

| File | What it holds |
|---|---|
| `PLAN.md` | Goal, scope, non-goals, its requirements and their status, and the slices (steps) that served it |
| `DESIGN.md` | How that part of the system works now, checked against the code |
| `DECISIONS.md` | The settled calls, from the umbrella's 48 decisions and the step archives |
| `OPEN.md` | Its open items, each checked against the code; fixed ones listed at the end |

Start with [ARCHITECTURE.md](../ARCHITECTURE.md) for the whole system, and the root
[OPEN.md](../../OPEN.md) for every open item in one list.

## The pillars

| Pillar | Outcome | Requirements |
|---|---|---|
| [P-A Web app and controls](P-A-web-app/PLAN.md) | One page, a prompt and controls, builds and shows a zone | 1–3 |
| [P-B Traversable](P-B-traversable/PLAN.md) | Every build walks: no pits, no islands, no cliffs; the walk gate proves it | 4–7 |
| [P-C Usable in RoF2 and EQEmu](P-C-rof2-eqemu/PLAN.md) | The output loads in the client and on a server | 8–11 |
| [P-D True-layout artifacts](P-D-true-layout/PLAN.md) | The map and sidecar show the zone as built | 12–14 |
| [P-E EverQuest look and feel](P-E-look-and-feel/PLAN.md) | Indistinguishable from a hand-made Classic–PoP zone | 15–17, 33 |
| [P-F Iterative feedback](P-F-iterative-feedback/PLAN.md) | Edit a build by prompt and keep what you liked | 18–20 |
| [P-G Engaging every time](P-G-engaging/PLAN.md) | Layouts worth exploring, different on every seed | 21–25 |
| [P-H World](P-H-world/PLAN.md) | Zones that sit in a larger world: sockets, outdoor dungeons, zone lines | draft H.1–4 |
| [Engineering](ENG-engineering/PLAN.md) | Tests, speed, tooling and docs that keep the rest moving | 26–32, proposed E1–E5 |

## Balance

A slice (one step spec, or a pre-step milestone) sits under the pillar whose outcome it mostly
moved; a step that helped two pillars is counted once, and the other pillar's PLAN names it
under "Also served by". Commits were counted with read-only `git log` at `c3d9b99`: a commit
belongs to a step by its `Task:` trailer (929 commits), else by the merge that brought it in
(228), else by the spec folder it touched or its subject's scope (161).

| Pillar | Slices | Steps | Commits | Share |
|---|---|---|---|---|
| P-A | 1 | 14 | 11 | 1% |
| P-B | 2 | M1, 33 | 134 | 10% |
| P-C | 1 | 17 | 27 | 2% |
| P-D | 1 | 1b | 35 | 3% |
| P-E | 13 | 1, 2, 3, 4, 8, 11, 15, 21, 23, 24, 25, 26, 29 | 413 | 31% |
| P-F | 2 | 16, 18 | 41 | 3% |
| P-G | 14 | 5, 6, 7, 9, 10, 13, 19, 20, 22, 27, 30, 31, 32, followups | 480 | 37% |
| P-H | 1 | 12 | 59 | 4% |
| Engineering | 3 | M0, 28, project-docs | 115 | 9% |
| **Attributed** | **38** | | **1315** | |
| Unattributed | | pre-spec phases, integration commits | 112 | |
| **All non-merge commits** | | | **1430** | |

(Three more, one in the umbrella spec and two tagged pre-spec, are left out of both rows.)

### What the balance shows

- **P-E and P-G hold 68% of the commits.** Since step 12, nearly every step has been look
  (P-E: caves, winding, clumps) or layout (P-G: Districts, races, halls, intrusion). Each was
  asked for and is real progress, but the other pillars have stood still.
- **P-C is proven only on paper.** One step built the SQL and door export; no zone has been
  loaded in the RoF2 client or applied on an EQEmu server (OPEN C-1), and seven of its twelve
  items wait on the user.
- **P-A has had one step** (14, the Controls), and its open list (17) is longer than its slice
  count suggests: the CLI lags the page, and some lists are hard-coded in the HTML.
- **Requirements no slice ever served:** 15's ConformanceReport and 16's normal maps (P-E),
  22's topology control (P-G), and decision 19's content renames (P-A).
- **P-H stopped after one step.** Step 12 built the World and Sockets; multi-zone worlds wait on
  a design review (OPEN H-1).

## Open items by pillar

| Pillar | Open | In flight | Parked | Waiting | Total | Already fixed |
|---|---|---|---|---|---|---|
| P-A | 12 | 0 | 4 | 1 | 17 | 3 |
| P-B | 10 | 2 | 1 | 1 | 14 | 6 |
| P-C | 4 | 0 | 1 | 7 | 12 | 3 |
| P-D | 3 | 1 | 0 | 1 | 5 | 3 |
| P-E | 29 | 0 | 3 | 5 | 37 | 15 |
| P-F | 6 | 0 | 0 | 1 | 7 | 4 |
| P-G | 27 | 1 | 2 | 7 | 37 | 10 |
| P-H | 3 | 0 | 0 | 1 | 4 | 1 |
| Engineering | 9 | 5 | 2 | 0 | 16 | 3 |
| **All** | **103** | **9** | **13** | **24** | **149** | **48** |
