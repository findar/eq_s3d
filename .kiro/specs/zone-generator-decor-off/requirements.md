# Requirements — zone-generator-decor-off (roadmap step 34)

> **STATUS: roadmap step 34, ready.** Drafted 2026-11-27 at master `0745b9e`. The user, after step 33's
> measure (decor placement 44% of generate time): "since decor placement takes so much of build time, can we disable it for now? it's not critical at the moment since we only worry about room generation and can decorate and optimize that part later as well"
> Task index: `tasks.md` (card format). Decisions: `archive.md`. This spec moves under its pillar with the
> others at the docs refactor's reconcile task.

## Requirements

1. **Decor is off unless asked for.** A generate whose plan doesn't choose a Decor level builds `none`: the
   CLI, the server, the web Controls (its default selection) and the rule and LLM planners. Choosing
   `sparse`, `normal` or `dense` still works exactly as before.
2. **Decor keeps working.** The tests that cover decor ask for it explicitly, so decor placement, its rules
   and its maps stay covered; the gate sweeps keep a way to run with decor (an option), and one decor sweep
   row stays in the gate tier.
3. **Measured.** Whole-generate median and max on step 33's job set (`scripts/generate_profile.py`)
   before and after; gate sweeps at master's count or better.
