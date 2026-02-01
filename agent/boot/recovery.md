# Recovery Procedures

Defines how to recover from failures and enter safe mode.

---

## Pre-Flight Checks

Before any self-modification, verify:
1. ✅ Can read `/boot/identity.md`
2. ✅ Can read `/boot/invariants.md`
3. ✅ Can write to `/logs/events/`
4. ✅ Can execute `echo "test"` successfully
5. ✅ Git repository is clean or changes are committed

If any check fails: **Do not proceed. Log failure and halt.**

---

## Safe Mode

### Triggers
- Invariants hash mismatch
- Repeated skill failure (>3 consecutive)
- Pre-flight check failure
- Explicit human command

### Safe Mode Behavior
1. Stop all task processing
2. Log entry to safe mode with reason
3. Execute only:
   - Health checks
   - Log writes
   - Status reporting
4. Wait for human intervention

### Exiting Safe Mode
Requires human task: `TASK: Exit safe mode`

---

## Recovery Scenarios

### Scenario: Bootstrap file corrupt
1. Check for `/boot/bootstrap.backup`
2. If exists: restore from backup
3. If not: enter safe mode, await human

### Scenario: Repeated skill failure
1. Disable the failing skill
2. Log to `/reflection/failures.md`
3. Continue with other tasks
4. Flag for human review

### Scenario: Empty summarization output
1. Halt memory modifications
2. Preserve raw logs
3. Log the failure
4. Retry with simpler summarization

### Scenario: Disk full
1. Enter safe mode
2. Log to stderr if possible
3. Do not attempt cleanup autonomously

### Scenario: LLM API unreachable
1. Retry with exponential backoff (max 3 attempts)
2. If still failing: pause task processing
3. Continue scheduled maintenance that doesn't require LLM
4. Log connectivity issue

---

## Rollback Procedure

1. Identify target snapshot (daily/weekly/monthly)
2. Verify snapshot integrity
3. Create pre-rollback snapshot
4. Restore files from snapshot
5. Reset git to snapshot commit
6. Run health checks
7. Log rollback completion

---

## Emergency Contacts

For issues requiring human intervention:
- Create blocked task with full context
- Write to `/reflection/failures.md`
- (Future: notification webhook)
