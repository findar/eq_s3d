# Design — zone-generator-hall-length (roadmap step 30)

## Measuring (task 1)

Stock hall length per kind: door-to-door length of passages between chambers, from
`scripts/stock_room_shapes.py`'s chambers and doorways (a passage's centreline length between
two doorways), as p10/p50/p90 per kind (built, cave, city), and the same over ours with
`scripts/grid_score.py` (`d2d p50`, already printed). The spread across stock zones of one kind
sets the range: `HALL_MIN` and `HALL_MAX` are the stock zone-median p10 and p90 over ours at 1,
rounded (a guess before measuring: 0.5 and 2.0).

Also measured: what each layout's spacing knob does to door-to-door length (Graph run factor,
classic separation gap and spread, outdoor Envelope fit), so task 2 scales the right one.

## The field (task 2)

`ai/schema.py` gains `hall_length` beside `winding` (`hall_length_value`, `HALL_MIN`,
`HALL_MAX`, dropped from the dict at 1). `ZoneSpec.hall_length` is written only when not 1.
`LayoutContext` carries it; the Graph engine multiplies the run (`run_factor x hall_length`),
the classic layout its gap/spread as task 1 found, the outdoor dungeon its spacing before the
Envelope fit. A throat's gap (`embed.THROAT_GAP`) is not scaled. Elevation is assigned after
placement and already bounds rise by run, so shorter halls carry less rise.

## Controls and words (task 3)

As step 26 task 3: a slider in `web/index.html`, `usesControl` entry, the build summary line,
`api.ts` field, the server's generate body and its LLM prompt line, rule-planner words with a
`match_hall_length`, the LLM planner schema.
