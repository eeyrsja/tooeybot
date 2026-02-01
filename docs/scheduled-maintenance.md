# Scheduled Maintenance

## Setting Up Cron Jobs

### Daily Maintenance (recommended: midnight)

```bash
# Edit crontab
crontab -e

# Add this line (runs at midnight every day):
0 0 * * * /home/stu/dev/tooeybot/scripts/daily-maintenance.sh

# Or for a specific time (e.g., 2 AM):
0 2 * * * /home/stu/dev/tooeybot/scripts/daily-maintenance.sh
```

### What Daily Maintenance Does

1. **Pre-flight checks** - Ensures agent can read/write critical files
2. **Daily summary** - Generates markdown summary from JSONL events
3. **Memory promotion** - Moves [PROMOTE] tagged items to long-term memory
4. **Snapshot** - Creates git commit and tag for rollback

### Manual Maintenance

```bash
cd ~/dev/tooeybot/runtime
source venv/bin/activate

# Run full maintenance
python -m tooeybot maintain

# Or individual commands:
python -m tooeybot summarize           # Generate today's summary
python -m tooeybot summarize -d 2026-01-31  # Specific date
python -m tooeybot snapshot -r "manual"    # Create snapshot
```

### Viewing Logs

```bash
# Maintenance log
tail -f ~/dev/tooeybot/agent/logs/maintenance.log

# Daily summaries
ls ~/dev/tooeybot/agent/logs/daily/
cat ~/dev/tooeybot/agent/logs/daily/2026-02-01.md
```

### Recall from Memory

```bash
# Search recent summaries and memory
python -m tooeybot recall "TASK-001"
python -m tooeybot recall "hello" --days 14
```

---

## Troubleshooting

### Cron not running?

```bash
# Check cron is running
systemctl status cron

# View cron logs
grep CRON /var/log/syslog

# Test the script manually
bash ~/dev/tooeybot/scripts/daily-maintenance.sh
```

### Maintenance failing?

```bash
# Check the maintenance log
cat ~/dev/tooeybot/agent/logs/maintenance.log

# Run health check
python -m tooeybot health

# Try individual steps
python -m tooeybot summarize
python -m tooeybot snapshot -r "test"
```
