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

## What's Next (Phase 1)

- Daily summary generation
- Memory promotion pipeline
- Snapshot creation
- Basic recovery procedures
