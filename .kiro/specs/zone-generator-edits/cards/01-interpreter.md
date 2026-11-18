# 1 — Edit ops and the rule interpreter

Index entry: `tasks.md` task 1. Requirement 1.1–1.4. Design "Ops".

## Goal
`ai/edits.py`: the op schema (`OPS`), `validate(ops, spec_doc)`, target resolution, and
`RuleEditInterpreter.interpret(text, spec_doc) -> (ops, notes, "rule")`. Pure: no server, no
build.

## Done when
- [ ] Every umbrella 18.2 op has a schema; validation clamps into range and rejects unknown ops
      and missing parameters with a reason. → verify: `python -m pytest tests/test_edit_interpreter.py -q`
- [ ] Targets resolve by id, role word and room type/kind; several rooms is ambiguous (the note
      lists them), none is a note naming op and target. Same command.
- [ ] A phrase table (at least 25 phrases, including "make the boss room bigger", "lock the
      way into the crypt", "redecorate the entrance", "less decor", "start over", two-clause
      text) gives the expected ops on a saved Graph dungeon spec. Same command.
- [ ] Hypothesis: any 0–2000 character string (empty, whitespace, any Unicode, control
      characters) returns valid ops and never raises; same text, same ops. Same command.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Use `re.fullmatch` for any whole-string check (lessons-learned "fullmatch"). Build the test
spec from a real build's `spec.json` shape (`ZoneSpec.to_dict`), not a hand-written dict.

## Result
