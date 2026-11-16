# Archive — zone-generator-partial-rebuild

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

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

## Follow-ups
