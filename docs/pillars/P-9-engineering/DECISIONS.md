# P-9 Engineering — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [1](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Scope: the umbrella designs and builds the full target system | Replaced the "retroactive baseline" framing with pillars and milestones; the milestone delivery plan was later replaced by the numbered roadmap steps |
| [13](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Security hardening for sessions | Bind to loopback only, a tighter CORS list, an optional access token when not on loopback, session caps. The session parts lapsed with [umbrella decision 37](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) |

## Slice decisions

| Slice | Where |
|---|---|
| [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | [`zone-generator-m0-hygiene/tasks.md`](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md), [`design.md`](../../../.kiro/specs/zone-generator-m0-hygiene/design.md) |
| [Step 28](../../../.kiro/specs/test-speed/tasks.md) | [`test-speed/archive.md`](../../../.kiro/specs/test-speed/archive.md) |
| Docs | [`project-docs/archive.md`](../../../.kiro/specs/project-docs/archive.md) ([project-docs decision 1](../../../.kiro/specs/project-docs/archive.md#decisions): the pillars; decision 2: the ID scheme) |

## Settled (don't relitigate)

- Tracker writes are single-writer and unconditional, solo or parallel.
- Don't push agent branches; push `master` after integration.
- Never start long-running processes from a blocking shell call.
- Don't add tests for their own sake; prefer fixing a root cause over loosening a test.
- Commit messages avoid the words the commit hook blocks ([lessons-learned](../../../.kiro/steering/lessons-learned.md#environment--tooling-windows--powershell)).
