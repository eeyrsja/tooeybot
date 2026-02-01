# Directory Map

Documents the agent's filesystem structure and purpose of each area.

---

## /agent (root)

### /boot
Core identity and configuration files. Mostly immutable.
- `identity.md` - Who the agent is
- `invariants.md` - Immutable rules (protected)
- `operating_principles.md` - Behavioral guidelines
- `context_policy.md` - How to assemble LLM context
- `recovery.md` - Failure recovery procedures
- `environment_awareness.md` - Understanding of runtime environment
- `bootstrap.md` - Startup sequence

### /memory
Agent's knowledge and beliefs.
- `working.md` - Short-term, task-focused memory
- `long_term.md` - Stable, curated knowledge
- `beliefs.md` - Structured claims with provenance
- `directory_map.md` - This file
- `/archive` - Old memory snapshots

### /skills
Skill definitions and lifecycle.
- `index.md` - Catalog of all skills
- `/core` - Human-authored meta-skills (immutable)
- `/candidates` - Skills being validated
- `/learned` - Promoted agent-authored skills
- `/deprecated` - Obsolete skills
- `/failed` - Failed validation attempts

### /logs
Structured logging.
- `/events` - JSONL append-only event logs
- `/daily` - Daily summary files (MD)
- `/weekly` - Weekly summary files (MD)
- `/health` - Health check results

### /tasks
Task management.
- `inbox.md` - Pending tasks
- `active.md` - Currently executing task
- `/completed` - Finished tasks
- `/blocked` - Tasks awaiting input

### /reflection
Self-improvement tracking.
- `improvements.md` - Proposed improvements
- `failures.md` - Failure analysis
- `open_questions.md` - Unresolved questions
- `drift_reports.md` - Identity/invariant drift detection

### /snapshots
Point-in-time backups.
- `/daily` - Last 7 days
- `/weekly` - Last 4 weeks
- `/monthly` - Last 12 months

### /scratch
Temporary working area. Can be cleared.

### /metrics
Optional Prometheus-format metrics.

---

*Last updated: 2026-02-01*
