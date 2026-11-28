# Design — zone-generator-layout-repair (roadmap step 33)

Written at master `0eeec16`. Verify against the code before each task: it moves.

- **Measure (task 1):** instrument `pipeline.generate_validated` and `generators/layout.py` with
  timers and refusal reasons behind an env flag or a script hook (no output change), run the job
  set (the 24-room timing set, the `--intrusion` sweep sample, the prompt seeds), and replay each
  gate failure's reason against the plan to classify it plan-visible or mesh-only.
- **Plan check (task 2):** a `generators/plancheck.py` over the laid-out `ZoneSpec` before
  geometry: corridor/corridor and corridor/room crossings in XY with Z overlap, opening spacing
  against doors, the narrowest way across each room floor at body width, breach span. Each check
  names the gate reason it predicts.
- **Repair (task 3):** at a plan-check failure, local moves first (Edgar's perturbation: move the
  room, reroute the corridor, drop and re-add one loop edge), scored by an energy of the check's
  violations; back up to the District's last good placement before redrawing the zone.
- **Contact energy (task 4):** a spring term between rooms the plan wants touching (breach
  pairs), so the breach bound is met at placement.
- Loops-first planning (Edgar's chain order, for designed one-way loops) and corridors as placed
  blocks are later slices, decided after task 3's numbers.
