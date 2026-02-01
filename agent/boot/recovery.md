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

### Using CLI (recommended)

```bash
# List available snapshots
cd ~/dev/tooeybot/runtime
source venv/bin/activate

# View recent snapshots
cd ~/dev/tooeybot/agent
git log --oneline --tags -10

# Restore to a specific snapshot
python -m tooeybot restore <commit-hash-or-tag>
```

### Manual Rollback

```bash
cd ~/dev/tooeybot/agent

# 1. Create backup of current state
git add -A
git commit -m "pre-rollback-backup"
git tag "pre-rollback-$(date +%Y%m%d-%H%M%S)"

# 2. Find the snapshot to restore
git log --oneline --tags -20

# 3. Restore files from that snapshot
git checkout <target-commit> -- .

# 4. Verify
python -m tooeybot health
```

### Daily Maintenance Recovery

If daily maintenance fails:

```bash
# Run maintenance manually
python -m tooeybot maintain

# Or run individual steps:
python -m tooeybot summarize
python -m tooeybot snapshot --reason "manual-recovery"
```

---

## Emergency Contacts

For issues requiring human intervention:
- Create blocked task with full context
- Write to `/reflection/failures.md`
- (Future: notification webhook)
