# 1 — Measure where a generate's time goes

Index entry: `tasks.md` task 1. Requirement 1.

## Goal
Know, with numbers, whether checking and repairing the plan would make generates faster, and by how much, before building it.

## Done when
- [ ] `scripts/generate_profile.py` runs a job set and reports per generate: time in plan Draws (count, and each refusal's reason), layout redraws inside a Draw (`DistrictSplitError`, `_resolve_conflicts` drops), mesh build, decor, gate, and retries. The hooks change no output: the 12-zone byte check matches master.
- [ ] Job set: the 24-room timing set (intrusion and sequential, 60 zones each), a 60-zone sample of the `--intrusion` sweep seed 31, the giant-fortress prompt on seeds 2020-2029, and 20 race-less zones across classic/graph/cave/city. Table of median/p90/max per phase in the commit body.
- [ ] Every refusal and gate failure classified: plan-visible (a 2D check on the laid-out spec could catch it, naming the check) or mesh-only. Share of total time each class costs.
- [ ] A projected saving if plan-visible failures were caught at plan time (time to the first passing plan) and if they were repaired locally (no redraw), with the assumptions stated.
- [ ] A recommendation for cards 2-4 (what to keep, cut or split), written as archive decision 2. If the projected saving is under 15% of whole-generate median, say so: the lead decides whether the step goes on.
- [ ] Quick tier.

## Pitfalls
- Run one heavy job at a time (`Get-CimInstance Win32_Process` for `pytest|sweep_`); timings under load are noise, so note the machine state.
- Build each byte-check zone in its own process (lessons-learned).

## Result
