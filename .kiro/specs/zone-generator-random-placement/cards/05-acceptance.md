# 5 — Acceptance section

Index entry: `tasks.md` task 5.

## Goal
`docs/ACCEPTANCE.md` gets "Step 27 — Random room placement", built and quoted.

## Done when
- [ ] Cases (decision 2: built and hewn keep the lattice): a cave and two outdoor dungeons
      (default and temple theme) on Graph, before (`b77d5a9`) and after, with room centres,
      grid score and what to walk in 3D (the way in faces the entrance room, stairs and Levels
      intact); a fortress and a warren on Graph showing they kept the lattice; a classic
      fortress and a city byte-identical to before. Also the fixes found on the way, each
      with its seed: the banner across an outline bend (outdoor seed 2 room_4), a corridor's
      floor under another Level's room (outdoor_cave corr_2), the shrine altar (outdoor
      dramatic 17 s1139996531), the treasure POI by a wall (s1801994134), and a 30-room
      outdoor dungeon's draw time (task 8).
- [ ] Every case built through `/api/generate` with `EQ_PATH` set passes the gate; every 3D item
      marked not looked at in 3D.

## Result
