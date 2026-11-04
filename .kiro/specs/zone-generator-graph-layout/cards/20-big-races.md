# 20 — Big races keep their loops; ogres get great halls

Index entry: `tasks.md` task 20. Requirements 6.1, 6.4. Added after task 15 (found by it).

## Goal
Two big-race findings from task 15. (1) Giant graph dungeons lose connections: measured (dungeon, Graph, `classic_eq`, seeds 0–11 × 10/15/20 rooms), Edge_Fidelity is 0.865 mean and 0.53 worst for giants against 0.99 for no race, ogre and troll, and built cycles per room 0.063 against 0.103 (classic band 0.07–0.25). (2) `classic_eq.toml`'s `great_hall` says it is for "ogres, giants", but its condition is `race_scale >= 1.5` and the ogre's scale is 1.4 (`generators/semantics.py` `RACE_SCALE`), so only giants get one. Find why giants lose loops (the 2.2 race scale applied after placement and the re-separation it forces? the `huge` great hall? both?), fix it at the cause, then make ogres get great halls without the same loss.

## Done when
- [ ] The cause is measured (giant with and without `great_hall`; race scale before vs after placement) and written in the commit body.
- [ ] Over the same sweep, giant and ogre graph builds keep mean Edge_Fidelity ≥ 0.95 and built cycles per room in the classic band; a test covers ogre and giant.
- [ ] Ogre builds apply `great_hall` (the condition and the rule's comment agree); the acceptance doc's ogre and giant cases (`docs/ACCEPTANCE.md` "Step 6 — Graph layouts") still build first try and say what they show.
- [ ] Classic is byte-identical (task 2 goldens); the tasks 5, 6 and 18 band tests pass.
      → verify: `python -m pytest tests/test_topology_embed.py tests/test_ruleset_classic_eq.py tests/test_layout_engine.py tests/test_graph_layout_build.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Placement sizes rooms from size classes at race scale 1; `semantics` multiplies by the race scale afterwards and Job B re-separates. If that is the cause, the placement should place at the final sizes (the context carries `race_scale`) and the race scale must not then be applied twice. Classic must not change.
- Rooms keep the floor area their class gives (task 9's rule); keep it.
- project.md: fix the cause, don't lower the bar.

## Result
