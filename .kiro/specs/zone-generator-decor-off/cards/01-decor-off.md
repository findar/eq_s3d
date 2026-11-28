# 1 — Decor off by default

Index entry: `tasks.md` task 1. Requirements 1, 2, 3.

## Done when
- [ ] The default Decor level is `none` everywhere a plan doesn't choose one: `ai/schema.DEFAULT_DECOR`, `pipeline._with_decor` (it reads the schema default, not `generators.decor.rules.DEFAULT_CONTROL`, which stays the rules' own default), the server's `/api/controls` default, the CLI `--decor` help, the web Controls' default selection, and the rule/LLM planners (a prompt that names clutter or props may still choose a level, as today).
- [ ] Decor tests ask for their level explicitly; nothing that tested decor now silently tests none. Sweeps gain `--decor <level>` (default none); one decor row (normal) stays in the gate tier.
- [ ] `scripts/generate_profile.py` on step 33's job set: whole-generate median/p90/max before and after (table in the commit body).
- [ ] Gate sweeps pass at master's count or better; zones that choose a Decor level byte-identical to master.
- [ ] Frontend build (`cd web && npx vite build`); quick tier; `-m gate` and the full suite alone at close.

## Pitfalls
- Step 31 task 8's spill (intruder decor in host rooms) only shows with decor on; its tests choose a level.

## Result
