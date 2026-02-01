# Skill: write_file

Version: 1.0.0
Status: core

## Purpose
Write content to a file on the filesystem.

## Triggers / When to use
- When creating new files
- When updating existing files
- When saving state or output

## Preconditions
- Target directory must exist (or be created)
- Path must be within allowed scope
- Must have write permission

## Dependencies
- log_event (for logging writes)

## Procedure
1. Validate path is within allowed scope
2. Create parent directories if needed
3. Write content to file (atomic if possible)
4. Verify write succeeded
5. Log the write operation
6. Return success/failure

## Commands and tools
- Python `open()` and `write()`
- `os.makedirs()` for directory creation
- Atomic write via temp file + rename (when critical)

## Validation / Self-test
- Test case: Write new file
  - Expected: file created with correct content
- Test case: Overwrite existing file
  - Expected: content replaced
- Test case: Write to read-only location
  - Expected: error with clear message

## Failure modes & recovery
- Permission denied → log error, return failure
- Disk full → log error, return failure
- Path outside scope → deny operation

## Notes
For critical files, consider backup before overwrite.

## Changelog
- 1.0.0 (2026-02-01): Initial version
