# eq_s3d

The project rules live in `.kiro/steering/`, written originally for Kiro. Kiro
isn't in use right now; `.kiro/` is simply where the specs and steering live.
Both steering files are always-on context:

@.kiro/steering/project.md
@.kiro/steering/lessons-learned.md

## Working a task

- Find work with `python scripts/task_status.py`. Specs in card format
  (`zone-generator-wilderness` so far) list their tasks in `tasks.md` and keep
  the detail in `cards/`. The rules are under "Card-format specs" in
  `project.md`.
- The prompts in `.kiro/agents/` (orchestrator, task-author, task-worker,
  reviewer, readiness) are dormant Kiro agents. Where they disagree with
  `project.md` about how to record results, `project.md` wins.
