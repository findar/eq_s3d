# 6 — The optional LLM interpreter

Index entry: `tasks.md` task 6. Requirement 1.5. Design "Ops".

## Goal
`ai/llm_edits.py` `LLMEditInterpreter`, used only when a key is configured, with
`ai/llm_planner.py`'s key handling; it falls back to the rule interpreter on any error, a schema
failure or 15 s without an answer. Task 4 picks it when a key is set.

## Done when
- [ ] With a fake client: good JSON gives validated, clamped ops; bad JSON, an exception and a
      timeout each give the rule interpreter's ops and name. → verify: `python -m pytest tests/test_llm_edits.py -q`
- [ ] With no key, nothing imports a provider SDK. Same command.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
No network in tests.

## Result
