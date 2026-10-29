"""
scripts/task_status.py
----------------------
Read the spec task indexes (``.kiro/specs/<feature>/tasks.md``) and report what
can be worked on now, so an agent or the orchestrator doesn't have to read
every task file.

A spec is in *card format* when its top-level tasks carry metadata bullets::

    - [ ] 2. Build a wilderness zone end to end
      - Card: [cards/02-build-end-to-end.md](cards/02-build-end-to-end.md)
      - Type: agent · Size: M · Depends: 1
      - Owns: generators/backends.py, main.py

Checkbox state is the only status: ``[ ]`` open, ``[-]`` in progress, ``[x]``
done. A task is *ready* when it is open and every ``Depends`` task is done.
Ready agent tasks whose ``Owns`` don't overlap can run in parallel worktrees.
Specs in the older free-form format are summarised as open/done counts only.

``--note`` builds a branch's integration note from git rather than prose: it
finds commits carrying the trailer ``Task: <spec>/<n>`` and prints them with
the Done-table row skeleton.

Usage::

    python scripts/task_status.py                              # every spec
    python scripts/task_status.py zone-generator-wilderness    # one spec
    python scripts/task_status.py zone-generator-wilderness --note 2-11
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / ".kiro" / "specs"

_TASK = re.compile(r"^- \[([ x\-])\]\*? (\d+)\. (.+?)\s*$")
_META = re.compile(r"^\s+- (Card|Type|Owns|Depends|Size|Where)\b")
_ANY_BOX = re.compile(r"^\s*- \[([ x\-])\]")
_STATE = {" ": "open", "-": "doing", "x": "done"}


@dataclass
class Task:
    num: int
    title: str
    state: str
    meta: dict = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return self.meta.get("Type", "agent")

    @property
    def depends(self) -> list[int]:
        raw = self.meta.get("Depends", "")
        return [int(n) for n in re.findall(r"\d+", raw)]

    @property
    def owns(self) -> list[str]:
        raw = self.meta.get("Owns", "")
        return [p.strip().rstrip("/") for p in raw.split(",") if p.strip()]


def parse(path: Path) -> tuple[list[Task], bool]:
    """Top-level tasks of a ``tasks.md`` and whether it is in card format."""
    tasks: list[Task] = []
    card_format = False
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _TASK.match(line)
        if m:
            tasks.append(Task(int(m.group(2)), m.group(3), _STATE[m.group(1)]))
            continue
        if tasks and _META.match(line):
            card_format = True
            body = line.strip()[2:]
            for part in body.split(" · "):
                key, _, value = part.partition(":")
                tasks[-1].meta[key.strip()] = value.strip()
    return tasks, card_format


def _overlaps(a: list[str], b: list[str]) -> bool:
    return any(x == y or x.startswith(y + "/") or y.startswith(x + "/")
               for x in a for y in b)


def parallel_groups(ready: list[Task]) -> list[list[Task]]:
    """Greedy grouping of ready agent tasks into sets with disjoint ``Owns``."""
    groups: list[list[Task]] = []
    for t in ready:
        for g in groups:
            if not any(_overlaps(t.owns, o.owns) for o in g):
                g.append(t)
                break
        else:
            groups.append([t])
    return groups


def report(spec: str) -> None:
    path = SPECS / spec / "tasks.md"
    if not path.exists():
        print(f"{spec}: no tasks.md")
        return
    tasks, card_format = parse(path)
    if not card_format:
        boxes = [m.group(1) for line in path.read_text(encoding="utf-8").splitlines()
                 if (m := _ANY_BOX.match(line))]
        print(f"{spec}: legacy format — {boxes.count('x')} done, "
              f"{boxes.count(' ') + boxes.count('-')} open (all checkboxes)")
        return

    done = {t.num for t in tasks if t.state == "done"}
    print(f"{spec}: {len(done)}/{len(tasks)} done")
    ready_agent: list[Task] = []
    for t in tasks:
        waiting = [d for d in t.depends if d not in done]
        if t.state == "done":
            note = ""
        elif t.state == "doing":
            note = "in progress"
        elif waiting:
            note = "blocked on " + ", ".join(map(str, waiting))
        elif t.kind == "human":
            note = "READY — waiting on you"
        else:
            note = "READY"
            ready_agent.append(t)
        mark = {"done": "x", "doing": "-", "open": " "}[t.state]
        print(f"  [{mark}] {t.num:>2}. {t.title}  ({t.kind}){'  — ' + note if note else ''}")

    if len(ready_agent) > 1:
        print("  Can run in parallel (disjoint Owns):")
        for g in parallel_groups(ready_agent):
            print("    - " + " + ".join(str(t.num) for t in g))


def _task_range(text: str) -> list[int]:
    nums: list[int] = []
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        nums.extend(range(int(lo), int(hi or lo) + 1))
    return nums


def note(spec: str, nums: list[int]) -> None:
    """Integration note for ``nums`` from commits trailed ``Task: <spec>/<n>``."""
    tasks = {t.num: t for t in parse(SPECS / spec / "tasks.md")[0]}
    all_hashes: list[str] = []
    for n in nums:
        out = subprocess.run(
            ["git", "log", "-E", f"--grep=^Task: {re.escape(spec)}/{n}$",
             "--format=%h %s"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            check=True,
        ).stdout.strip().splitlines()
        title = tasks[n].title if n in tasks else "?"
        print(f"Task {n}. {title} — {len(out)} commit(s)")
        for line in out:
            print(f"    {line}")
        all_hashes += [line.split()[0] for line in out]

    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    print()
    print("Done-table row (fill in the summary):")
    print(f"| {spec} tasks {','.join(map(str, nums))} | <summary> | "
          f"{len(all_hashes)} commits, head `{head}` |")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("specs", nargs="*", help="spec folder names (default: all)")
    ap.add_argument("--note", metavar="RANGE",
                    help="print an integration note for tasks, e.g. 2-11 or 2,5")
    args = ap.parse_args(argv)

    specs = args.specs or sorted(p.name for p in SPECS.iterdir() if p.is_dir())
    if args.note:
        if len(specs) != 1:
            ap.error("--note needs exactly one spec")
        note(specs[0], _task_range(args.note))
        return 0
    for spec in specs:
        report(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
