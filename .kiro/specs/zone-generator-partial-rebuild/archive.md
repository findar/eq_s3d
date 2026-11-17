# Archive — zone-generator-partial-rebuild

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | A room can keep its own decor seed; a plan's room seeds stay hashable | `7a00516`, `d847e28`, `189c626` |
| 2 | A rebuild makes the next version of the same zone | `3eb99c9`, `5057439` |
| 3 | A decor rebuild builds from the parent's saved stages, equal to a full build | `1f74017`, `e32bfb6`, `24667e2` |
| 4 | The shell's gate result and the map outline kept per TER; the gate re-checks only the Props | `44ad8c8`, `ea1284d`, `6ff5156` |
| 5 | Versions in the header, rerolls and Use in zone in the page | `9f9d9b2`, `0a9d27d`, `24667e2` |
| 6, 8 | First look and acceptance pass, signed off 2026-11-17 | `4e401c9` |
| 7 | Acceptance section; thorough 3248 passed; live timings in the commit | `ce72a95`, `b005e80` |
| 9 | Close | this commit |

## Decisions

Decided 2026-11-15: the user chose "Partial rebuild (M4)" for step 16 and agreed to the shape
the lead proposed from the timings ("Sounds good").

1. **A reroll makes a new version of the same zone** (`v<n+1>`), not a new zone; v1 is what
   Generate makes and is unchanged.
2. **A partial rebuild must equal a full build** of the same request and seeds, byte for byte
   (footer aside). Speed never buys a different zone.
3. **The gate re-checks only what changed**, against the shell's kept result, and must give the
   full gate's verdict; without a kept result it runs the full gate. The wilderness keeps its
   full bowl gate.
4. **A room can keep its own decor seed** (Use in zone in the room view). Its bare decision
   still comes from the zone's decor seed, so no other room changes.
5. **Not in this step:** Sessions, chat edits, the `RuleEditInterpreter`, undo/redo (the rest of
   M4). They build on the versions.
6. **A room the zone's draw leaves bare stays as the zone drew it** (task 1): its own decor seed
   isn't used, so Use in zone can't change the bare cap. Only rooms take a room decor seed.

## Follow-ups

- The rest of M4 on these versions: Sessions, chat edits through the `RuleEditInterpreter`, undo/redo (decision 5).
- Carried from step 15, still open: `scripts/stage.py` `decor_stage` keeping its own copy of the bare cap; the room view's slow first call in a fresh server; Sites not in the room view.
