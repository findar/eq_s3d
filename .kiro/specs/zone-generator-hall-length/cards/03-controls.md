# 3 — Controls, server and planner words

Index entry: `tasks.md` task 3. Requirement 4, design "Controls and words".

## Done when
- [ ] A **Hall length** slider (`HALL_MIN`–`HALL_MAX`, default 1) in the Controls for dungeon,
      city and outdoor dungeon, in the build summary, sent by `api.ts`, passed by the server.
- [ ] Rule-planner words (`match_hall_length`) and the LLM planner schema; the server's LLM
      prompt line names the field.
- [ ] `tests/test_hall_length_words.py` for the words and the server pass-through.
- [ ] `cd web; npx tsc --noEmit` shows no new errors (pre-existing ones listed); the frontend
      builds (`npx vite build`).
- [ ] Quick tier green.

## Pitfalls
- lessons-learned "Movement keys must be suppressed while typing".
- Words must not fire inside other phrases ("long" alone is too common: use "long halls",
  "long corridors", "long passages").

## Result
