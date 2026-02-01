# Skill: execute_command

Version: 1.0.0
Status: core

## Purpose
Execute shell commands in the sandbox environment and capture results.

## Triggers / When to use
- When a task requires running a shell command
- When gathering system information
- When installing packages or tools
- When manipulating files via shell utilities

## Preconditions
- Command must not violate invariants
- Working directory must exist
- Required tools must be available

## Dependencies
- log_event (for logging execution)

## Procedure
1. Validate command against invariants (no forbidden operations)
2. Log the command about to be executed
3. Execute command with timeout
4. Capture stdout, stderr, exit code
5. Log the result
6. Return structured result

## Commands and tools
- `subprocess.run()` in Python runtime
- Timeout enforcement
- Exit code capture

## Validation / Self-test
- Test case: `echo "hello"`
  - Expected: stdout="hello\n", exit_code=0
- Test case: `false`
  - Expected: exit_code=1
- Test case: `sleep 100` with 1s timeout
  - Expected: timeout error

## Failure modes & recovery
- If command times out → kill process, log timeout, return error
- If command not found → log error, return not_found status
- If permission denied → log error, do not retry

## Notes
This is a core skill. It must always be available and must always log.

## Changelog
- 1.0.0 (2026-02-01): Initial version
