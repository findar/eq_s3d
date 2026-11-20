# 6 — Acceptance section

Index entry: `tasks.md` task 6.

## Goal
`docs/ACCEPTANCE.md` "Step 23 — Winding tunnels" covers:
- a cave dungeon's tunnels in 3D and on the map;
- a warren's tunnels;
- a ramp tunnel between Levels;
- a stair and a bridge, still straight;
- a built fortress, unchanged;
- decor in a tunnel.

## Done when
- [ ] The section is written, and every case was run through the route with its seed on agent
      servers (8020–8050 only). → verify: `git show HEAD -- docs/ACCEPTANCE.md`
- [ ] Thorough run: `python -m pytest tests/ -q --hypothesis-profile=thorough`, with any failures
      named in the commit body.

## Pitfalls
- Leave the user's servers (8000, 5173) and the lead's (8010, 5180) alone.
- Never write "Vite" or "dev server" in a commit message.

## Result
