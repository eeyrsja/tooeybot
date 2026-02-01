# Skill: read_file

Version: 1.0.0
Status: core

## Purpose
Read the contents of a file from the filesystem.

## Triggers / When to use
- When needing to examine file contents
- When loading configuration or state
- When gathering context for a task

## Preconditions
- File must exist
- File must be readable
- Path should be within allowed directories

## Dependencies
- log_event (for logging access)

## Procedure
1. Validate path is within allowed scope
2. Check file exists
3. Read file contents
4. Log the read operation
5. Return contents (or error)

## Commands and tools
- Python `open()` and `read()`
- Path validation

## Validation / Self-test
- Test case: Read existing file
  - Expected: contents returned
- Test case: Read non-existent file
  - Expected: error with clear message
- Test case: Read file outside /agent
  - Expected: denied (policy dependent)

## Failure modes & recovery
- File not found → return clear error
- Permission denied → log and return error
- File too large → read with size limit, warn

## Notes
Core skill for all file operations.

## Changelog
- 1.0.0 (2026-02-01): Initial version
