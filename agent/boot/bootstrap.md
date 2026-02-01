# Bootstrap

Initial startup sequence for the agent.

---

## Startup Sequence

### 1. Environment Check
```
- Verify /agent directory structure exists
- Verify boot files are readable
- Verify logs directory is writable
- Check invariants hash (if baseline exists)
```

### 2. Load Identity
```
- Read /boot/identity.md
- Read /boot/invariants.md
- Read /boot/operating_principles.md
```

### 3. Initialize Logging
```
- Open/create today's event log: /logs/events/YYYY-MM-DD.jsonl
- Log startup event
```

### 4. Load Memory State
```
- Read /memory/working.md
- Read /skills/index.md
- Note last processed task
```

### 5. Check for Recovery
```
- If safe mode flag exists: enter safe mode
- If incomplete task exists: assess and resume or abandon
- If pre-flight checks fail: enter safe mode
```

### 6. Begin Main Loop
```
- Process inbox tasks by priority
- Execute scheduled maintenance if due
- Idle if no work pending
```

---

## First-Run Initialization

On first run (no existing state):
1. Create directory structure if missing
2. Initialize empty memory files
3. Initialize empty skills index
4. Create baseline invariants hash
5. Log initialization complete
6. Ready to accept tasks

---

## Shutdown Sequence

### Graceful Shutdown
1. Complete current action (if safe)
2. Log shutdown event
3. Commit any pending git changes
4. Write working memory state
5. Exit cleanly

### Forced Shutdown
1. Log forced shutdown (if possible)
2. State may be incomplete
3. Next startup will detect and recover

---

## Version
- Bootstrap version: 1.0.0
- Last updated: 2026-02-01
