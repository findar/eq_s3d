# 5 — Tooling: task_status and the heavy-run lock

Index entry: `tasks.md` task 5. Requirement 6.

## Done when
- [ ] `task_status.py` finds slices under pillars and active specs; `--check` flags archive follow-ups missing from `OPEN.md` and specs not linked from a pillar; a test.
- [ ] `scripts/heavy.py run -- <command>` takes a machine-wide lock (a file lock under the main checkout's `.git`), waits its turn, and logs who holds it; steering tells agents to wrap gate, full and sweep runs in it.

## Result
