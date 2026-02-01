# Skill: log_event

Version: 1.0.0
Status: core

## Purpose
Log structured events to the JSONL event log.

## Triggers / When to use
- After every command execution
- When task state changes
- When errors occur
- When significant observations are made

## Preconditions
- Event log directory must exist
- Must have write permission to logs

## Dependencies
- None (this is the base logging skill)

## Procedure
1. Construct event object with required fields
2. Add timestamp (ISO 8601)
3. Serialize to JSON
4. Append to today's log file
5. Ensure newline termination

## Event Schema
```json
{
  "timestamp": "ISO 8601",
  "event_type": "skill_execution|task_update|error|note|...",
  "context": { ... },
  "execution": { ... },
  "outcomes": { ... },
  "metadata": { ... }
}
```

## Commands and tools
- Python `json.dumps()`
- File append mode

## Validation / Self-test
- Test case: Log simple event
  - Expected: event appended to today's file
- Test case: Log with all fields
  - Expected: valid JSON on single line

## Failure modes & recovery
- Cannot write to log → print to stderr, continue if possible
- Invalid event data → log error about logging failure

## Notes
This skill must NEVER fail silently. Logging is an invariant.

## Changelog
- 1.0.0 (2026-02-01): Initial version
