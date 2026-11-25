# 2 — Probe the shortest corridor

Index entry: `tasks.md` task 2. Requirement 2, design "Throats".

## Goal
Know how short a cave corridor can be before any reader (mesh flush, outline, gate, decor
RoomContexts, map, transitions) fails, so task 3 can pick the throat's length.

## Done when
- [ ] `scripts/throat_probe.py` builds cave Graph zones (10–16 rooms, seeds 2000–2009) with a
      monkeypatched spacing that forces some edges to a target door-to-door length (0, 4, 8,
      16, 24 u and one corridor width), runs each through the gate, and prints per length:
      builds passing, and the first failing check with its seed.
- [ ] `scripts/grid_score.py --shapes` prints the share of edges whose door-to-door is ≤ one
      corridor width ("throat"), read as `stock_room_shapes.py` reads "direct".
- [ ] The shortest length every reader takes, and any reader that needs a fix to go shorter,
      recorded as a decision in `archive.md` (one or two lines; the table in the commit body).

## Pitfalls
- No generator code: monkeypatch from the script. If a reader fails at every short length,
  say which and stop; task 3 widens its Owns only on the lead's word.
- lessons-learned "Geometry / fields": flush openings, ramp subdivision (a short corridor
  between rooms at different heights can't carry a rise; throats join rooms on one floor).

## Result
