# Engineering — decisions

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 1 | Scope: the umbrella designs and builds the full target system | Replaced the "retroactive baseline" framing with pillars and milestones; the milestone Delivery plan was later superseded by the roadmap steps |
| 13 | Security hardening for sessions | Loopback bind, tightened CORS, optional bearer token off loopback, session caps. The session parts lapsed with decision 37 |

## Slice decisions

| Slice | Where |
|---|---|
| M0 | [`zone-generator-m0-hygiene/tasks.md`](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md), [`design.md`](../../../.kiro/specs/zone-generator-m0-hygiene/design.md) |
| Step 28 | [`test-speed/archive.md`](../../../.kiro/specs/test-speed/archive.md) |
| Docs | [`project-docs/archive.md`](../../../.kiro/specs/project-docs/archive.md) (1: pillars are P-A to P-G plus World and Engineering) |

## Settled (don't relitigate)

- Tracker writes are single-writer and unconditional, solo or parallel.
- Don't push agent branches; push `master` after integration.
- Never start long-running processes from a blocking shell call.
- Don't add tests for their own sake; prefer fixing a root cause over loosening a test.
- Commit messages avoid the words the commit hook blocks.
