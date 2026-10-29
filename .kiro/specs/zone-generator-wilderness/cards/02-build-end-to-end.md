# 2 — Build a wilderness zone end to end (behind a dev flag)

Index entry: `tasks.md` task 2.

## Goal
The wilderness generator (`generators/wilderness/`) is complete, but only tests
call it. A wilderness build still goes through the old "noise over the room
footprint" terrain, so nobody has ever seen a Karana. Wire the real pipeline
into the build, so that `python main.py generate` produces a `.eqg` + `.glb` you
can open in the viewer:

  plan → matrix → rewrite → synth → bowl → TER

Keep wilderness hidden from normal users behind a dev flag until it has been
looked at (tasks 4 and 10). Flat preview colours are enough for now; textures,
the water plane and the sidecar fields come in later tasks.

## Done when
- [ ] With `EQ_S3D_DEV_WILDERNESS=1` set, `is_enabled("wilderness")` is true.
      Without the flag, behaviour is exactly as today. Put the check in
      `generators/zone_types.py` so the CLI, server and pipeline all see it through
      `is_enabled`. Don't add a second gate.
      → verify: a new test in `tests/test_wilderness_build.py` (monkeypatch the env).
- [ ] `python main.py generate k1 --zone-type wilderness --seed 1337` (flag set)
      writes `.eqg`, `.glb` and `.zone.json`. A new `--edges` option
      (e.g. `N=zoneline,E=river`; sides not named default to `mountain`)
      reaches `build_matrix`.
      → verify: run it; paste the artifact list into Result.
- [ ] Wilderness builds are gated by `check_bowl` in `generate_validated` (no
      rooms → the room gate doesn't apply). A failed bowl check rejects the
      attempt like any other gate failure.
      → verify: test that a wilderness build reports the bowl gate as passed.
- [ ] Each region type gets its own TER material (plains, rim, water, lava,
      zoneline), each with its own base colour, so the preview tells them apart.
      → verify: the `.glb` has ≥ 3 materials for a mixed-edge build.
- [ ] Dungeon, city and plain-terrain builds are unchanged.
      → verify: `pytest tests/test_terrain.py tests/test_properties_build.py -q`
      plus the seed-1337 plain-terrain checksum in `archive.md`.
- [ ] `python -m pytest tests/ -q` is green.

## Approach (suggested, not binding)
- Add `generators/wilderness/build.py` with one entry point,
  `build_wilderness_ter(spec, ter_name, ter_version)`. `TerrainBackend.build`
  calls it when the spec carries a wilderness payload and otherwise does exactly
  what it does today. Later tasks (6, 7) extend this module, not `backends.py`.
- `ZoneSpec` gains ONE defaulted field (e.g. `wilderness: Optional[dict] = None`
  holding biome + edges). When it is empty it must not appear in `to_dict()`, so
  dungeon/city output stays byte-identical.
- `build_bowl_ter` loops over vertices in Python. That's fine at 60×60, but
  prefer the vectorised `_heightfield_to_ter` from `generators/field/terrain.py`
  if the grid grows (lessons-learned: "never reintroduce a per-voxel Python loop").

## Not in this task
Web/server edge controls (task 3), water plane (6), biome textures (7), sidecar
advisory fields (8), enabling for real (11).

## Result
<!-- worker: one line -->
