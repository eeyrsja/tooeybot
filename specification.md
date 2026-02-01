# v2 Specification: Bash-Native Self-Evolving Agent with Markdown Memory & Skills

## 0. Executive summary

We are building a **persistent autonomous agent** that lives inside a **sandboxed Linux environment** and uses:

* **Real bash + Linux tooling** (no tool gateway)
* **Root inside sandbox** (for package installs, services, cron)
* A cloud LLM for planning/reasoning
* A local **filesystem-as-mind** model:

  * Memory and beliefs as Markdown
  * Skills as Markdown procedures
  * Logs as structured JSONL + Markdown summaries
  * Self-improvement proposals as Markdown
* Self-maintenance loops (cron/heartbeat) that:

  * execute tasks
  * log outcomes
  * summarise and compress memory
  * detect contradictions and drift
  * propose and/or apply improvements within bounds

The innovation is the **agent’s internal operating system**: how it learns new skills, maintains coherent memory, and evolves safely over time.

---

## 1. Scope, goals, and non-goals

### 1.1 Goals

1. **Autonomous task execution** from a structured inbox.
2. **Persistent memory** that remains usable weeks/months later.
3. **Self-authored skills** with explicit validation gates.
4. **Coherence preservation** (belief tracking + contradiction detection).
5. **Context relevance** (tiered context assembly, adaptive optimisation).
6. **Debuggability & recovery** (safe mode, snapshots, rollback).
7. **Observability** (structured logs, health checks, metrics hooks).
8. **Controlled exploration** (curiosity budget to prevent runaway behaviour).

### 1.2 Non-goals (initially)

* Full autonomy for external messaging (email/WhatsApp/etc.) without explicit governance.
* Unbounded network access and self-provisioned identities without constraints.
* Complex UI: MVP uses filesystem/CLI interaction.

---

## 2. Architecture overview

### 2.1 Component model

**A) Sandbox Node (the “organism”)**

* Linux environment with bash
* Root inside sandbox allowed
* Persistent volume for `/agent`
* Cron available inside sandbox

**B) Agent Runtime (the process)**

* Reads tasks and state from `/agent`
* Builds LLM context
* Calls cloud LLM
* Executes actions via shell
* Writes logs, summaries, memory updates, and skill updates

**C) LLM Connector**

* API client invoked from inside sandbox
* Stateless inference; the agent provides context each call
* Returns plans, actions, reflections, and proposed file changes

**D) Filesystem Knowledge Base**

* Markdown is the primary representation
* Event logs are structured JSONL for analysis
* Git provides history, diffs, rollback

### 2.2 Design principle: “Identity and capability are data, not code”

* Most behaviour is defined by:

  * `/boot/*.md` (invariants, identity, operating principles)
  * `/skills/**/*.md` (procedures and QA)
  * `/memory/**/*.md` (beliefs, working state, long-term knowledge)

The core code remains small and stable.

---

## 3. Directory structure (canonical v2)

```
/agent
  /boot
    identity.md
    operating_principles.md
    invariants.md
    context_policy.md
    recovery.md
    environment_awareness.md
    bootstrap.md
    bootstrap.backup
  /memory
    working.md
    long_term.md
    beliefs.md
    directory_map.md
    /archive
  /skills
    index.md
    /core          # human-authored meta-skills, immutable in MVP
    /candidates    # drafted skills undergoing validation
    /learned       # agent-authored promoted skills
    /deprecated    # obsolete or replaced
    /failed        # failed validation attempts (for learning)
  /logs
    /events        # JSONL append-only
    /daily         # daily summaries (MD)
    /weekly        # weekly summaries (MD)
    /health        # coherence/drift checks (MD + JSON)
  /tasks
    inbox.md
    active.md
    /completed
    /blocked
  /reflection
    improvements.md
    failures.md
    open_questions.md
    drift_reports.md
  /snapshots
    /daily
    /weekly
    /monthly
  /metrics         # optional: Prometheus textfile outputs
  /scratch
  /tools
    (helper scripts, optional)
```

Notes:

* This structure is a **baseline**; the agent may propose structural changes (subject to invariants).
* `/skills/core` and `/boot/invariants.md` are treated as **immutable** until later phases.

---

## 4. Boot and invariants

### 4.1 Immutable invariants (`/boot/invariants.md`)

Human-authored and protected. The agent must treat these as non-modifiable.

Minimum invariants:

* Purpose boundaries / identity constraints
* Logging requirements (what must always be logged)
* Minimum skill validation standards
* Human interaction protocol (task formatting, what needs approval)
* Self-modification thresholds (what is allowed autonomously vs proposal-only)
* Recovery and safe-mode requirements

### 4.2 Drift detection

* Store a cryptographic hash of key immutable files (at least `identity.md` and `invariants.md`) in a separate metadata file (or signed commit/tag).
* Weekly check compares current hash vs expected.
* Any mismatch → write report to `/reflection/drift_reports.md` and enter safe mode (policy-dependent).

### 4.3 Environment awareness (`/boot/environment_awareness.md`)

The agent explicitly documents:

* it is in a sandbox
* it may have root inside sandbox
* it cannot assume host access
* network policy constraints (as configured)

This isn’t enforcement; it’s operational clarity.

---

## 5. Memory model (with coherence controls)

### 5.1 Memory artifacts

1. **Event logs** (ground truth): `/logs/events/YYYY-MM-DD.jsonl`
2. **Working memory**: `/memory/working.md` (short, task-adjacent)
3. **Long-term memory**: `/memory/long_term.md` (stable, curated)
4. **Beliefs**: `/memory/beliefs.md` (structured claims with provenance)
5. **Summaries**: `/logs/daily/*.md`, `/logs/weekly/*.md`
6. **Health checks**: `/logs/health/*` (coherence, drift, integrity results)

### 5.2 Beliefs file schema (`/memory/beliefs.md`)

Beliefs are *not* free text. Each entry is a structured claim:

```markdown
# Beliefs

## B-000123
Claim: The agent must log every shell command it executes in events JSONL.
Confidence: 0.98
Status: active | contested | deprecated
Type: invariant-derived | observed | inferred | external
Provenance:
  - Source: /boot/invariants.md
    Evidence: hash:...
Last_validated: 2026-01-31
Contradictions:
  - None
Notes: ...
```

### 5.3 Memory promotion pipeline

Define an explicit pipeline:

* **Event** → captured in JSONL (always)
* **Observation** → extracted into daily summary
* **Repeated observation / validated result** → added to long-term memory
* **Stable claim** → added to beliefs with provenance
* **Repeated successful procedure** → candidate skill drafted

### 5.4 Coherence and contradiction detection

A core weekly process:

* Scan `working.md`, `long_term.md`, `beliefs.md`, recent summaries
* Identify conflicting claims (same subject, incompatible statements)
* Mark contested beliefs and propose resolutions:

  * re-validate via experiments or source checks
  * downgrade confidence
  * split belief into conditional forms (“if X then Y”)

Outputs:

* `/logs/health/coherence-YYYY-Www.md`
* Updates to `beliefs.md` statuses

---

## 6. Event logging (structured JSONL)

### 6.1 Append-only event schema

Each event is one JSON object in JSONL:

```json
{
  "timestamp": "2026-01-31T10:42:12Z",
  "event_type": "skill_execution|task_update|self_modification|error|note",
  "context": {
    "task_id": "TASK-001",
    "triggering_skill": "learned/web_research@1.2.0",
    "intent": "Fetch and summarise documentation for X"
  },
  "execution": {
    "commands": [
      {"cmd": "curl", "args": ["-L", "https://example.com"], "cwd": "/agent/scratch"}
    ],
    "exit_codes": [0],
    "duration_ms": 842
  },
  "outcomes": {
    "files_modified": [
      {"path": "/agent/memory/working.md", "hash_after": "sha256:..."}
    ],
    "artifacts_created": [],
    "observations": "Key points found..."
  },
  "metadata": {
    "llm_model": "cloud-model-id",
    "context_tokens": 5800,
    "confidence": 0.84,
    "curiosity_spend": 0.1
  }
}
```

### 6.2 Why this matters

This enables quantitative self-analysis later:

* skill failure rates
* time-to-complete
* which context elements correlate with success
* when memory contradictions increase

---

## 7. Skills system (quality-gated and composable)

### 7.1 Skill taxonomy and lifecycle

```
/skills
  /core        # immutable meta-skills, human-authored
  /candidates  # drafts undergoing validation
  /learned     # promoted skills
  /deprecated  # replaced/obsolete
  /failed      # failed validation attempts
```

### 7.2 Skill file template

Every skill uses a standard structure:

```markdown
# Skill: <name>
Version: <semver>
Status: core|candidate|learned|deprecated|failed

## Purpose
...

## Triggers / When to use
...

## Preconditions
...

## Dependencies
- core/filesystem_navigation@1.0.0
- learned/html_to_text@0.3.0

## Procedure
1. ...
2. ...

## Commands and tools
- ...

## Validation / Self-test
- Test case A: ...
- Expected outcome: ...
- Evidence capture: file/log references

## Failure modes & recovery
- If X fails → do Y
- If repeated failure (>3) → mark candidate as failed and log

## Notes
...

## Changelog
- 1.2.0 ...
```

### 7.3 Skill composability

Skills can chain other skills via dependencies. The agent should prefer:

* small, reusable primitives
* composed workflows over monolith skills

### 7.4 Promotion gate (required before moving candidate → learned)

A candidate skill must satisfy:

1. **Self-test executed** with documented outcomes
2. **LLM peer review** against operating principles and invariants
3. **Regression check** (does not break critical flows)
4. **Failure modes documented**
5. **Minimum successful uses: 3** separate uses logged in events JSONL
6. Update `/skills/index.md` with confidence rating

### 7.5 Deprecation policy

* Skills unused for N review cycles are flagged
* Deprecated skills retained but not used by default
* If replaced, include pointer to successor skill

---

## 8. Context window management (tiered and adaptive)

### 8.1 Context tiers (defined in `/boot/context_policy.md`)

**ALWAYS**

* `/boot/identity.md`
* `/boot/operating_principles.md`
* `/boot/invariants.md` (or a short invariant summary + hash)
* current task spec
* `/skills/index.md`

**HIGH**

* `/memory/working.md`
* last daily summary
* any skills explicitly invoked for this task (their Markdown)

**MEDIUM**

* keyword-matched sections from:

  * `/memory/long_term.md`
  * `/memory/beliefs.md`
* last weekly summary (if relevant)

**LOW / ON-DEMAND**

* event logs (queried/searchable, not auto-loaded)
* archives

### 8.2 Budget and overflow behaviour

* Define a maximum context budget (tokens or bytes).
* If exceeded:

  * compress lower-tier content on-the-fly
  * prefer beliefs over narrative summaries
  * prefer recent over old

### 8.3 Context profiling skill

The agent maintains a record of:

* what files/sections were loaded
* which were cited in reasoning or actions (heuristic: references in output)
* outcomes success/failure

This allows the agent to tune context assembly over time.

Outputs:

* `/logs/health/context-profile-YYYY-Www.json`

---

## 9. Human interaction protocol

### 9.1 Task inbox format (`/tasks/inbox.md`)

Strict task blocks:

```markdown
---
task_id: TASK-001
priority: high|medium|low
deadline: 2026-02-10T00:00:00Z   # optional
context: |
  Background and constraints.
---

# Task description
...

## Success criteria
- ...
```

### 9.2 Agent task response format

Created at `/tasks/completed/TASK-001.md` (or `/tasks/blocked/`):

```markdown
# Task: TASK-001
Status: ✅ Complete | ⏸ Blocked | ❌ Failed
Completed: 2026-01-31

## Summary
...

## Approach
- Skills used: ...
- Key decisions: ...

## Artifacts
- /agent/... (files created/updated)

## Commands executed (high level)
- (summarised; detailed in events log)

## Learnings
- New skill drafted/promoted: ...

## Follow-ups
- ...
```

---

## 10. Orchestration, autonomy, and scheduling

### 10.1 Operating loop (conceptual)

1. Ingest tasks and deadlines
2. Assemble context per policy
3. Plan actions (LLM)
4. Execute via shell
5. Log structured events
6. Update working memory
7. Summarise daily/weekly
8. Run health checks (coherence/drift)
9. Propose improvements (and optionally apply allowed ones)

### 10.2 Cron-based maintenance (inside sandbox)

Minimum jobs:

* Daily summary generation
* Weekly review + coherence check
* Snapshot creation
* Skill deprecation scan
* Context profiling compilation
* Curiosity budget enforcement (reset windows)

---

## 11. Goal stability and drift control

### 11.1 Stable goal model

* Goals exist as:

  * identity (purpose)
  * current tasks
  * standing maintenance duties (summaries, health checks)

### 11.2 Drift detection

Weekly:

* Compare current identity hash against baseline
* Compare invariants hash against baseline
* Look for large semantic changes in identity text even if hash unchanged (if allowed edits exist)

Report anomalies and optionally enter safe mode.

---

## 12. Recovery, safe mode, and snapshots

### 12.1 Recovery document (`/boot/recovery.md`)

Defines safe mode procedures:

* If `bootstrap.md` corrupt → load `bootstrap.backup`
* If repeated skill failure (>3) → disable skill, log to `/reflection/failures.md`
* If summarisation produces empty output → halt modifications, preserve raw logs
* Pre-flight checks before any self-modification:

  * can read identity + invariants
  * can write event logs
  * can write daily summary
  * can execute a known safe command
* Emergency rollback uses snapshots + git

### 12.2 Snapshot policy

* Daily snapshots: keep last 7
* Weekly snapshots: keep last 4
* Monthly snapshots: keep last 12

Snapshot metadata must include:

* timestamp
* git commit hash
* brief reason (scheduled / pre-modification / post-failure)

---

## 13. Observability and metrics

### 13.1 Health checks (minimum)

* Sandbox self-check: expected OS characteristics, expected mounts, expected permissions
* Logging integrity: can append events, logs not empty
* Coherence check: contradictions count, contested beliefs count
* Task loop health: time since last successful tick
* Skill system health: candidates pending, failures, deprecated count

### 13.2 Metrics output

Optional but recommended:

* Write Prometheus textfile metrics to `/agent/metrics/*.prom`
  Examples:
* `agent_tasks_completed_total`
* `agent_skill_failures_total{skill="..."}`
* `agent_contradictions_total`
* `agent_context_tokens_avg`

---

## 14. Curiosity budget (runaway prevention without killing innovation)

Curiosity is allowed but bounded.

Define:

* a daily exploration budget (time/requests/tokens)
* optionally per-domain budgets:

  * web exploration
  * tool installation experimentation
  * skill refactoring

Curiosity spend is logged in event metadata. If budget exhausted:

* exploration tasks defer
* only inbox and maintenance tasks continue

---

## 15. Phased delivery plan (revised MVP)

### Phase 0 — Validation

* Static agent; no self-modification
* Executes tasks from inbox
* Structured JSONL logs
* Proves sandbox + LLM integration + command execution

Success: reliable task execution + logs

### Phase 1 — Memory

* working + long-term memory
* daily summaries
* snapshotting + basic recovery

Success: recall facts from 1 week ago

### Phase 2 — Skills

* execute pre-written core skills
* draft candidate skills
* manual promotion (or gated auto-promotion)

Success: writes and uses a new skill once

### Phase 3 — Autonomy

* automatic promotion gates
* weekly coherence checks + drift reports
* deprecation policy
* curiosity budget

Success: operates 1 month with <1 human intervention/week

### Phase 4 — Evolution

* self-improvement proposals
* controlled memory reorganisation
* architecture mutation proposals (not auto-applied to invariants/core)

Success: proposes and validates meaningful improvements

---

## 16. “Done” criteria for v2 MVP

The system qualifies as “v2 MVP” when:

* It runs continuously in sandbox with full bash
* It installs and maintains its own dependencies
* It logs every meaningful action in structured JSONL
* It produces daily + weekly summaries
* It maintains beliefs with provenance
* It detects contradictions and produces health reports
* It drafts skills, validates them, promotes them, and deprecates them
* It can recover from self-inflicted errors using snapshots/git
* It stays within curiosity budget and does not spiral