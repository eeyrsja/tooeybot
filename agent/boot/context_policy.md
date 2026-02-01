# Context Policy

Defines how context is assembled for LLM calls.

---

## Token Budget
- **Maximum context**: 8000 tokens (adjustable per model)
- **Reserved for response**: 2000 tokens
- **Available for context**: 6000 tokens

---

## Context Tiers

### ALWAYS (must include)
| File | Priority | Max Tokens |
|------|----------|------------|
| `/boot/identity.md` | 1 | 500 |
| `/boot/invariants.md` | 2 | 800 |
| `/boot/operating_principles.md` | 3 | 600 |
| Current task specification | 4 | 1000 |
| `/skills/index.md` | 5 | 400 |

### HIGH (include if space permits)
| File | Priority | Max Tokens |
|------|----------|------------|
| `/memory/working.md` | 6 | 800 |
| Last daily summary | 7 | 500 |
| Invoked skill definitions | 8 | 600 |

### MEDIUM (include if relevant and space permits)
| File | Priority | Max Tokens |
|------|----------|------------|
| Relevant sections of `/memory/long_term.md` | 9 | 400 |
| Relevant beliefs from `/memory/beliefs.md` | 10 | 300 |
| Last weekly summary | 11 | 300 |

### LOW (on-demand only)
- Event logs (queried, not auto-loaded)
- Archived memory
- Deprecated skills

---

## Overflow Behavior

When context exceeds budget:
1. Truncate LOW tier first
2. Compress MEDIUM tier (extract key points only)
3. Summarize HIGH tier if still over
4. Never truncate ALWAYS tier

---

## Context Profiling

Track for optimization:
- Files loaded per task
- Files actually referenced in reasoning
- Correlation with task success/failure

Output: `/logs/health/context-profile-YYYY-Www.json`
