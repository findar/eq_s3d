# Requirements — zone-generator-races-followups (roadmap step 32)

> **STATUS: roadmap step 32, ready.** Drafted 2026-11-27 at master `fbfe1a9`, the lead's pick on
> the user's "You pick" after the step 31 close. Task index: `tasks.md` (card format).
> Decisions: `archive.md`.

## Introduction

Step 31 gave each District its own race, intruder Districts that break into their host through
breaches, and one-way drops. Its first look shortened goblin-sized links to goblin hall lengths
(task 17), which cost breaches: District pairs with 2+ links fell from 82% to 68%, and 3 of 10
giant-fortress prompt seeds join the goblins by their Threshold alone. The user's ask was
overlap ("i would expect there to be overlap"), so the breach rate is the main item. Two smaller
step 31 follow-ups ride along: the map's inferred "return" mark, and the build-order leak that
makes the same seed build differently after another zone in the same process.

## Requirements

1. **Breaches fit again.** Over the `--intrusion` sweep (seed 31), pairs with 2+ links are back
   to at least 80%, and at least 9 of 10 giant-fortress prompt seeds (2020-2029) have a goblin
   breach, with links still inside step 31 task 17's bars (p50 in 10.7-30.2 H, max at most
   164 H, each in its own race's H). Dramatic Levels and corridor conflicts are named causes to
   address.
2. **The map's returns are real.** A drop's flush return is recorded in the spec (written only
   when set), and the map marks it from that record. The District labels keep clear of the
   legend.
3. **Same seed, same build.** A zone builds byte-identical whether built alone or after other
   zones in the same process.
4. **Gate and bands.** The intrusion and `--pair` sweeps pass at master's count or better;
   bands under 5% per key; zones without a District race byte-identical, except where
   requirement 3 changes them (named); draw time within the ~5 min budget.
