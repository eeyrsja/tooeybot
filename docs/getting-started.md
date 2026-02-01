# Tooeybot Phase 0 - Getting Started

## What We Built

### Agent Filesystem (`/agent`)
The agent's "mind" - a structured directory of Markdown files:
- **Boot files**: Identity, invariants, operating principles
- **Memory**: Working memory, long-term memory, beliefs
- **Skills**: Core skills (execute_command, read_file, write_file, log_event)
- **Tasks**: Inbox, active task, completed/blocked folders
- **Logs**: JSONL event logs (ground truth)
- **Reflection**: Improvements, failures, open questions

### Python Runtime (`/runtime`)
The agent's "body" - code that brings the mind to life:
- **Agent**: Main loop, tick execution, task processing
- **LLM**: Abstracted provider layer (Ollama, OpenAI, Anthropic)
- **Executor**: Shell command execution with logging
- **Context**: Assembles relevant context for LLM calls
- **Tasks**: Parses inbox, manages task lifecycle
- **Logger**: Structured JSONL event logging

---

## Quick Start

### 1. Setup the Ubuntu VM
Follow [environment-setup.md](environment-setup.md) to create your VirtualBox VM.

### 2. Copy Files to VM
From Windows PowerShell:
```powershell
# Copy everything to VM
scp -P 2222 -r d:\dev\tooeybot youruser@127.0.0.1:~/
```

### 3. Run Setup Script
SSH into VM and run:
```bash
cd ~/tooeybot
chmod +x scripts/setup-vm.sh
./scripts/setup-vm.sh
```

### 4. Configure
```bash
cd ~/tooeybot/runtime
cp config.example.yaml config.yaml
# Edit config.yaml - set Ollama URL if running on host
```

If Ollama runs on Windows host, use:
```yaml
ollama:
  base_url: http://10.0.2.2:11434  # VirtualBox NAT gateway to host
```

### 5. Test
```bash
source venv/bin/activate
python -m tooeybot health
```

### 6. Add a Task
Edit `/agent/tasks/inbox.md`:
```markdown
---
task_id: TASK-001
priority: high
context: |
  First test task for the agent.
---

# Hello World Test

Create a file called hello.txt in /agent/scratch with the content "Hello from Tooeybot!"

## Success criteria
- File /agent/scratch/hello.txt exists
- Contains the text "Hello from Tooeybot!"
```

### 7. Run a Tick
```bash
python -m tooeybot tick
```

---

## Phase 0 Success Criteria

✅ Sandbox + LLM integration working  
✅ Command execution with logging  
✅ Structured JSONL event logs  
✅ Task parsing and lifecycle  
✅ Basic context assembly  

---

## Phase 1 — Memory

### New Commands

```bash
# Generate daily summary from events
python -m tooeybot summarize
python -m tooeybot summarize --date 2026-01-31

# Create a git snapshot
python -m tooeybot snapshot
python -m tooeybot snapshot --reason "before-experiment"

# Run full daily maintenance
python -m tooeybot maintain

# Recall from memory/summaries
python -m tooeybot recall "TASK-001"
python -m tooeybot recall "error" --days 14

# Restore from snapshot
python -m tooeybot restore snapshot-2026-02-01_120000
```

### Memory Promotion

To promote items from working memory to long-term memory, add `[PROMOTE]` or `[IMPORTANT]` to any line in `/agent/memory/working.md`:

```markdown
## Session Notes
- Learned that gpt-5-mini doesn't support temperature parameter [PROMOTE]
- TASK-001 completed successfully
```

When `maintain` runs, these tagged items move to long-term memory.

### Setting Up Cron

See [scheduled-maintenance.md](scheduled-maintenance.md) for cron setup.

Quick setup:
```bash
chmod +x ~/dev/tooeybot/scripts/daily-maintenance.sh
crontab -e
# Add: 0 0 * * * /home/stu/dev/tooeybot/scripts/daily-maintenance.sh
```

### Phase 1 Success Criteria

✅ Daily summary generation  
✅ Git-based snapshots with tags  
✅ Memory promotion pipeline  
✅ Restore from snapshot  
✅ Recall from summaries  

---

## What's Next (Phase 2)

- Execute pre-written core skills
- Draft candidate skills
- Manual skill promotion (or gated auto-promotion)
