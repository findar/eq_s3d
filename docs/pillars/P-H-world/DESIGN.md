# P-H World — design (living)

How the World works now, inside one zone. Checked against the code at `c3d9b99`.

## The World (`generators/world.py`)

`world_for(zone_type, seed, biome=...)` makes a `World`:

- the **Terrain** (height grid, `bowl_heights`, rim-seal and playable masks, cell types), or none
  for a dungeon or city;
- the water level, regions, the Spawn and the placed **Landform** (an outdoor dungeon's hill);
- the **Sockets** it offers: typed attach points.

| Socket kind | Made for | What attaches |
|---|---|---|
| `root` | dungeon, city | the whole room layout |
| `hillside` | outdoor dungeon | the dungeon; the Attach stage picks the Mouth inside it |
| `ground` | wilderness, outdoor dungeon | the area Sites attach to (its `keep_clear` holds earlier shapes) |
| `site` | wilderness, outdoor dungeon (World version 2) | one Site per point; points in Groups with Free radii and a hill flag |
| `door` | reserved | read, but nothing makes one |

The JSON form (`<name>.world.json`) is versioned (`VERSION = 2`; another version is refused,
naming both) and stable: sorted keys, floats written exactly as `repr`, grids one row to a line.
`world_of(spec)` remakes the World from a spec's own Landform.

## The Attach stage (`generators/stages.py`)

Sockets attach in a fixed order, `root`, `hillside`, `ground`, `site`, so the Apron digs the
ground before Sites see it and Sites keep off the Tunnel and Apron.

- `attach_rooms` reads only the World (height grid, Spawn), the Socket, the plan's room fields
  and the seed: no landscape is synthesised and no TER built.
- `attach_sites` reads the World with every earlier Attachment's `TerrainEdit`s applied.
- `apply_edits(world, attachments)` is the one function that applies terrain edits, used by the
  Attach stage and by the Build when it makes the TER, so the two can't disagree.
- `<name>.attach.json` saves the Attachments; `scripts/stage.py` runs one stage from saved
  hand-offs.

## Seeds and blame

`seed` makes the World (and trees), `rooms_seed` the rooms and Sites, `decor_seed` the Props;
each defaults to `seed`, so a build naming none is byte-identical to before step 12. On a gate
failure with a random seed the pipeline rerolls only the stage it blames, at most twice per
World (P-B).

## Not yet

One zone per World; one dungeon per World; no zone lines. `tunnel_doors` and `sidecar_block` in
`generators/outdoor_dungeon.py` still call `landscape_for` instead of reading the World.
