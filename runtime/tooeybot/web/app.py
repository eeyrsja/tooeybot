"""
FastAPI Web Application for Tooeybot

Provides a web interface for:
- Task management (create, view, complete)
- Memory browsing (working, long-term)
- Belief management (view, add, contest)
- Skills management (list, draft, promote)
- Logs and health monitoring
- Agent control (tick, maintenance, snapshots)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import tooeybot components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooeybot.config import load_config, Config
from tooeybot.agent import Agent
from tooeybot.tasks import TaskManager, TaskParser, TaskOrigin
from tooeybot.skills import SkillManager
from tooeybot.beliefs import BeliefManager
from tooeybot.maintenance import MaintenanceManager
from tooeybot.cycle import CycleHistory
from tooeybot.curiosity import CuriosityManager
from tooeybot.budgets import AgentBudgets, BudgetEnforcer


app = FastAPI(title="Tooeybot", description="Autonomous Agent Web Interface")

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Global config (loaded on startup)
config: Optional[Config] = None
agent_home: Optional[Path] = None


def get_config() -> Config:
    """Get or load configuration."""
    global config, agent_home
    if config is None:
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        config = load_config(config_path)
        agent_home = config.agent_home
    return config


def get_agent_home() -> Path:
    """Get agent home path."""
    get_config()
    return agent_home


# ============================================================================
# Template Helpers
# ============================================================================

def format_datetime(dt: datetime) -> str:
    """Format datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M")


def read_file_safe(path: Path) -> str:
    """Read file or return empty string."""
    try:
        return path.read_text()
    except:
        return ""


# ============================================================================
# Dashboard
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    home = get_agent_home()
    cfg = get_config()
    
    # Get task counts
    task_mgr = TaskManager(home)
    pending_tasks = task_mgr.get_pending_tasks()
    active_task = task_mgr.get_active_task()
    
    completed_dir = home / "tasks" / "completed"
    completed_count = len(list(completed_dir.glob("*.md"))) if completed_dir.exists() else 0
    
    # Get belief count
    belief_mgr = BeliefManager(home)
    beliefs = belief_mgr.get_all_beliefs()
    
    # Get skill counts
    skill_mgr = SkillManager(home)
    skills = skill_mgr.load_all_skills()
    
    # Get recent events
    events = []
    events_dir = home / "logs" / "events"
    if events_dir.exists():
        event_files = sorted(events_dir.glob("*.jsonl"), reverse=True)[:1]
        for ef in event_files:
            for line in ef.read_text().strip().split("\n")[-10:]:
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except:
                        pass
    events = events[-10:][::-1]  # Last 10, newest first
    
    # Health check
    agent = Agent(cfg)
    health = agent.health_check()
    
    # Phase 2: Get cycle and budget info
    cycle_history = CycleHistory(home)
    budgets = AgentBudgets(
        max_iterations_per_task=cfg.budgets.max_iterations_per_task,
        max_consecutive_failures=cfg.budgets.max_consecutive_failures,
        max_actions_without_progress=cfg.budgets.max_actions_without_progress,
        curiosity_enabled=cfg.curiosity.enabled,
        max_curiosity_tasks_per_day=cfg.curiosity.max_tasks_per_day,
    )
    budget_enforcer = BudgetEnforcer(budgets, home)
    budget_enforcer.load_state()
    budget_status = budget_enforcer.get_status_summary()
    
    # Get curiosity stats
    curiosity_mgr = CuriosityManager(home, budgets, budget_enforcer)
    curiosity_stats = curiosity_mgr.get_daily_stats()
    
    # Get cycle count for active task
    cycle_count = 0
    if active_task:
        cycle_count = cycle_history.get_cycle_count(active_task.task_id)
    
    # Task origin breakdown
    task_origins = task_mgr.count_by_origin()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "pending_count": len(pending_tasks),
        "active_task": active_task,
        "completed_count": completed_count,
        "belief_count": len(beliefs),
        "skill_count": len(skills),
        "recent_events": events,
        "health": health,
        # Phase 2 additions
        "budget_status": budget_status,
        "curiosity_stats": curiosity_stats,
        "cycle_count": cycle_count,
        "task_origins": task_origins,
    })


# ============================================================================
# Tasks
# ============================================================================

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_list(request: Request):
    """Task management page."""
    home = get_agent_home()
    task_mgr = TaskManager(home)
    
    pending = task_mgr.get_pending_tasks()
    active = task_mgr.get_active_task()
    
    # Get completed tasks
    completed = []
    completed_dir = home / "tasks" / "completed"
    if completed_dir.exists():
        for f in sorted(completed_dir.glob("*.md"), reverse=True)[:20]:
            completed.append({
                "id": f.stem,
                "path": f,
                "content": f.read_text()[:200]
            })
    
    # Get blocked tasks
    blocked = []
    blocked_dir = home / "tasks" / "blocked"
    if blocked_dir.exists():
        for f in sorted(blocked_dir.glob("*.md"), reverse=True)[:10]:
            blocked.append({
                "id": f.stem,
                "path": f,
                "content": f.read_text()[:200]
            })
    
    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "pending": pending,
        "active": active,
        "completed": completed,
        "blocked": blocked,
    })


@app.post("/tasks/create")
async def create_task(
    request: Request,
    task_id: str = Form(...),
    priority: str = Form("medium"),
    description: str = Form(...),
    context: str = Form(""),
    success_criteria: str = Form("")
):
    """Create a new task."""
    home = get_agent_home()
    inbox_path = home / "tasks" / "inbox.md"
    
    # Format success criteria
    criteria_lines = ""
    if success_criteria.strip():
        for line in success_criteria.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("-"):
                line = f"- {line}"
            criteria_lines += f"{line}\n"
    
    # Build task block
    task_block = f"""
---
task_id: {task_id}
priority: {priority}
{f'context: |{chr(10)}  {context}' if context.strip() else ''}
---
{description}

## Success criteria
{criteria_lines if criteria_lines else '- Task completed successfully'}
"""
    
    # Append to inbox
    current = inbox_path.read_text() if inbox_path.exists() else "# Task Inbox\n\n"
    inbox_path.write_text(current + "\n" + task_block)
    
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/tick")
async def run_tick(request: Request):
    """Run a single agent tick."""
    cfg = get_config()
    agent = Agent(cfg)
    result = agent.tick()
    
    return RedirectResponse(url="/tasks", status_code=303)


# ============================================================================
# Cycles (Phase 2)
# ============================================================================

@app.get("/cycles", response_class=HTMLResponse)
async def cycles_page(request: Request, task_id: str = ""):
    """Cycle history viewer page."""
    home = get_agent_home()
    cfg = get_config()
    
    cycle_history = CycleHistory(home)
    
    # Get list of tasks with cycle history
    history_dir = home / "tasks" / "history"
    tasks_with_history = []
    if history_dir.exists():
        for hf in sorted(history_dir.glob("*.jsonl"), reverse=True)[:20]:
            task_id_from_file = hf.stem
            cycle_count = sum(1 for _ in hf.read_text().strip().split("\n") if _.strip())
            tasks_with_history.append({
                "task_id": task_id_from_file,
                "cycles": cycle_count,
            })
    
    # Get cycles for selected task
    cycles = []
    selected_task = task_id
    if task_id:
        history = cycle_history.load_history(task_id)
        for cycle in history:
            cycles.append({
                "cycle_id": cycle.cycle_id,
                "phase": cycle.phase.value,
                "action_type": cycle.action.action_type.value if cycle.action else None,
                "success": cycle.observation.success if cycle.observation else None,
                "progress": cycle.reflection.progress_made if cycle.reflection else None,
                "decision": cycle.decision.value,
                "timestamp": cycle.timestamp.strftime("%H:%M:%S"),
            })
    
    # Get budget status
    budgets = AgentBudgets(
        max_iterations_per_task=cfg.budgets.max_iterations_per_task,
        max_consecutive_failures=cfg.budgets.max_consecutive_failures,
    )
    budget_enforcer = BudgetEnforcer(budgets, home)
    budget_enforcer.load_state()
    budget_status = budget_enforcer.get_status_summary()
    
    return templates.TemplateResponse("cycles.html", {
        "request": request,
        "tasks_with_history": tasks_with_history,
        "selected_task": selected_task,
        "cycles": cycles,
        "budget_status": budget_status,
    })


@app.get("/cycles/{task_id}", response_class=HTMLResponse)
async def cycles_for_task(request: Request, task_id: str):
    """View cycles for a specific task."""
    return await cycles_page(request, task_id)


# ============================================================================
# Curiosity (Phase 2)
# ============================================================================

@app.get("/curiosity", response_class=HTMLResponse)
async def curiosity_page(request: Request):
    """Curiosity system dashboard."""
    home = get_agent_home()
    cfg = get_config()
    
    budgets = AgentBudgets(
        curiosity_enabled=cfg.curiosity.enabled,
        max_curiosity_tasks_per_day=cfg.curiosity.max_tasks_per_day,
        max_curiosity_depth=cfg.curiosity.max_depth,
        min_curiosity_value_threshold=cfg.curiosity.min_value_threshold,
    )
    budget_enforcer = BudgetEnforcer(budgets, home)
    curiosity_mgr = CuriosityManager(home, budgets, budget_enforcer)
    
    # Get stats
    stats = curiosity_mgr.get_daily_stats()
    
    # Get recent curiosity log entries
    log_entries = []
    curiosity_log = home / "logs" / "curiosity.jsonl"
    if curiosity_log.exists():
        for line in reversed(curiosity_log.read_text().strip().split("\n")[-50:]):
            if line.strip():
                try:
                    log_entries.append(json.loads(line))
                except:
                    pass
    
    # Get curiosity-origin tasks
    task_mgr = TaskManager(home)
    curiosity_tasks = [
        t for t in task_mgr.get_pending_tasks()
        if t.origin == TaskOrigin.CURIOSITY
    ]
    
    return templates.TemplateResponse("curiosity.html", {
        "request": request,
        "stats": stats,
        "log_entries": log_entries[:20],
        "curiosity_tasks": curiosity_tasks,
        "config": {
            "enabled": cfg.curiosity.enabled,
            "max_per_day": cfg.curiosity.max_tasks_per_day,
            "max_depth": cfg.curiosity.max_depth,
            "min_value": cfg.curiosity.min_value_threshold,
        },
    })


# ============================================================================
# Memory
# ============================================================================

@app.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request):
    """Memory browser page."""
    home = get_agent_home()
    
    working = read_file_safe(home / "memory" / "working.md")
    long_term = read_file_safe(home / "memory" / "long_term.md")
    directory_map = read_file_safe(home / "memory" / "directory_map.md")
    
    # Get active beliefs for summary
    belief_mgr = BeliefManager(home)
    beliefs = [b for b in belief_mgr.get_all_beliefs() if b.status == "active"]
    
    return templates.TemplateResponse("memory.html", {
        "request": request,
        "working_memory": working,
        "longterm_memory": long_term,
        "directory_map": directory_map,
        "beliefs": beliefs,
    })


@app.post("/memory/working")
async def update_working_memory(request: Request, content: str = Form(...)):
    """Update working memory."""
    home = get_agent_home()
    (home / "memory" / "working.md").write_text(content)
    return RedirectResponse(url="/memory", status_code=303)


@app.post("/memory/working/clear")
async def clear_working_memory(request: Request):
    """Clear working memory."""
    home = get_agent_home()
    (home / "memory" / "working.md").write_text("# Working Memory\n\n*Cleared*\n")
    return RedirectResponse(url="/memory", status_code=303)


@app.post("/memory/longterm")
async def update_longterm_memory(request: Request, content: str = Form(...)):
    """Update long-term memory."""
    home = get_agent_home()
    (home / "memory" / "long_term.md").write_text(content)
    return RedirectResponse(url="/memory", status_code=303)


@app.post("/memory/directory-map")
async def update_directory_map(request: Request, content: str = Form(...)):
    """Update directory map."""
    home = get_agent_home()
    (home / "memory" / "directory_map.md").write_text(content)
    return RedirectResponse(url="/memory", status_code=303)


# ============================================================================
# Beliefs
# ============================================================================

@app.get("/beliefs", response_class=HTMLResponse)
async def beliefs_page(request: Request):
    """Beliefs management page."""
    home = get_agent_home()
    belief_mgr = BeliefManager(home)
    
    beliefs = belief_mgr.get_all_beliefs()
    
    # Group by status
    by_status = {"active": [], "contested": [], "deprecated": []}
    for b in beliefs:
        by_status.setdefault(b.status, []).append(b)
    
    return templates.TemplateResponse("beliefs.html", {
        "request": request,
        "beliefs": beliefs,
        "by_status": by_status,
    })


@app.post("/beliefs/add")
async def add_belief(
    request: Request,
    claim: str = Form(...),
    confidence: float = Form(0.7),
    belief_type: str = Form("external"),
    source: str = Form("")
):
    """Add a new belief."""
    home = get_agent_home()
    belief_mgr = BeliefManager(home)
    
    belief_mgr.add_belief(
        claim=claim,
        confidence=confidence,
        belief_type=belief_type,
        source=source or "Web UI"
    )
    
    return RedirectResponse(url="/beliefs", status_code=303)


@app.post("/beliefs/{belief_id}/contest")
async def contest_belief(request: Request, belief_id: str, reason: str = Form(...)):
    """Contest a belief."""
    home = get_agent_home()
    belief_mgr = BeliefManager(home)
    
    belief_mgr.contest_belief(belief_id, reason)
    
    return RedirectResponse(url="/beliefs", status_code=303)


# ============================================================================
# Skills
# ============================================================================

@app.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request):
    """Skills management page."""
    home = get_agent_home()
    skill_mgr = SkillManager(home)
    
    skills = skill_mgr.load_all_skills()
    
    # Group by status
    by_status = {"core": [], "learned": [], "candidate": []}
    for key, skill in skills.items():
        stats = skill_mgr.get_skill_stats(skill.name)
        skill.stats = stats
        by_status.setdefault(skill.status, []).append(skill)
    
    # Get promotable candidates
    promotable = skill_mgr.get_promotable_candidates()
    
    return templates.TemplateResponse("skills.html", {
        "request": request,
        "skills": skills,
        "by_status": by_status,
        "promotable": promotable,
    })


@app.post("/skills/draft")
async def draft_skill(
    request: Request,
    name: str = Form(...),
    purpose: str = Form(...),
    triggers: str = Form(...),
    procedure: str = Form(...)
):
    """Draft a new skill."""
    home = get_agent_home()
    skill_mgr = SkillManager(home)
    
    skill_mgr.draft_skill(
        name=name,
        purpose=purpose,
        triggers=triggers,
        procedure=procedure
    )
    
    return RedirectResponse(url="/skills", status_code=303)


@app.post("/skills/{name}/promote")
async def promote_skill(request: Request, name: str):
    """Promote a candidate skill."""
    home = get_agent_home()
    skill_mgr = SkillManager(home)
    
    result = skill_mgr.promote_skill(name)
    
    return RedirectResponse(url="/skills", status_code=303)


# ============================================================================
# Logs
# ============================================================================

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    level: str = "",
    event_type: str = "",
    limit: int = 50
):
    """Logs viewer page."""
    home = get_agent_home()
    cfg = get_config()
    
    # Get event logs
    all_events = []
    events_dir = home / "logs" / "events"
    if events_dir.exists():
        for ef in sorted(events_dir.glob("*.jsonl"), reverse=True)[:7]:
            for line in ef.read_text().strip().split("\n"):
                if line.strip():
                    try:
                        all_events.append(json.loads(line))
                    except:
                        pass
    
    # Apply filters
    events = all_events
    if level:
        events = [e for e in events if e.get("level") == level]
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]
    
    events = events[-limit:][::-1]  # Most recent first
    
    # Calculate daily summary
    from datetime import date
    today = date.today().isoformat()
    today_events = [e for e in all_events if e.get("timestamp", "").startswith(today)]
    daily_summary = {
        "tasks_completed": len([e for e in today_events if e.get("event_type") == "task_completed"]),
        "skills_used": len([e for e in today_events if e.get("event_type") == "skill_used"]),
        "beliefs_formed": len([e for e in today_events if e.get("event_type") == "belief_formed"]),
        "errors": len([e for e in today_events if e.get("level") == "ERROR"]),
    }
    
    # Get health info
    agent = Agent(cfg)
    health_result = agent.health_check()
    health = {
        "overall": "healthy" if all(v.get("ok", True) for v in health_result.values()) else "degraded",
        "checks": {k: "ok" if v.get("ok", True) else "warning" for k, v in health_result.items()},
        "warnings": [v.get("message", "") for v in health_result.values() if not v.get("ok", True)]
    }
    
    # Get coherence report if available
    belief_mgr = BeliefManager(home)
    coherence = belief_mgr.coherence_check()
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "events": events,
        "filter_level": level,
        "filter_type": event_type,
        "limit": limit,
        "daily_summary": daily_summary,
        "health": health,
        "coherence": coherence,
    })
    summaries = []
    daily_dir = home / "logs" / "daily"
    if daily_dir.exists():
        for sf in sorted(daily_dir.glob("*.md"), reverse=True)[:7]:
            summaries.append({
                "date": sf.stem,
                "content": sf.read_text()
            })
    
    # Get health reports
    health_reports = []
    health_dir = home / "logs" / "health"
    if health_dir.exists():
        for hf in sorted(health_dir.glob("*.md"), reverse=True)[:5]:
            health_reports.append({
                "name": hf.stem,
                "content": hf.read_text()
            })
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "events": events,
        "summaries": summaries,
        "health_reports": health_reports,
    })


# ============================================================================
# Control Panel
# ============================================================================

@app.get("/control", response_class=HTMLResponse)
async def control_page(request: Request):
    """Agent control panel."""
    home = get_agent_home()
    cfg = get_config()
    
    # Get agent health
    agent = Agent(cfg)
    health = agent.health_check()
    
    # Determine agent status
    task_mgr = TaskManager(home)
    active_task = task_mgr.get_active_task()
    agent_status = "running" if active_task else "idle"
    
    # Get last tick time from events
    last_tick = None
    events_dir = home / "logs" / "events"
    if events_dir.exists():
        for ef in sorted(events_dir.glob("*.jsonl"), reverse=True)[:1]:
            for line in reversed(ef.read_text().strip().split("\n")):
                if line.strip():
                    try:
                        event = json.loads(line)
                        if event.get("event_type") in ["tick_started", "tick_completed"]:
                            last_tick = event.get("timestamp", "")[:19]
                            break
                    except:
                        pass
            if last_tick:
                break
    
    # Get snapshots (git tags with 'snapshot-' prefix)
    import subprocess
    snapshots = []
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "snapshot-*"],
            cwd=str(home),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            snapshots = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
            snapshots = sorted(snapshots, reverse=True)[:10]
    except:
        pass
    
    # Get last snapshot time
    last_snapshot = snapshots[0] if snapshots else None
    
    return templates.TemplateResponse("control.html", {
        "request": request,
        "agent_status": agent_status,
        "last_tick": last_tick,
        "health": health,
        "agent_home": str(home),
        "llm_model": cfg.llm_model if hasattr(cfg, 'llm_model') else "gpt-4o-mini",
        "version": "0.3.0",
        "uptime": "N/A",
        "tick_enabled": False,
        "tick_interval": 60,
        "next_maintenance": None,
        "last_snapshot": last_snapshot,
        "snapshots": snapshots,
    })


@app.post("/control/tick")
async def control_tick(request: Request):
    """Run agent tick."""
    cfg = get_config()
    agent = Agent(cfg)
    result = agent.tick()
    return {"success": result.success, "message": result.message}


@app.post("/control/maintenance")
async def control_maintenance(request: Request):
    """Run maintenance."""
    home = get_agent_home()
    maint = MaintenanceManager(home)
    result = maint.run_daily_maintenance()
    return {"success": result["success"]}


@app.post("/control/snapshot")
async def control_snapshot(request: Request, reason: str = Form("manual")):
    """Create snapshot."""
    home = get_agent_home()
    maint = MaintenanceManager(home)
    result = maint.create_snapshot(reason=reason)
    return RedirectResponse(url="/control", status_code=303)


@app.post("/control/coherence-check")
async def control_coherence_check(request: Request):
    """Run coherence check on beliefs."""
    home = get_agent_home()
    belief_mgr = BeliefManager(home)
    result = belief_mgr.coherence_check()
    return RedirectResponse(url="/logs", status_code=303)


@app.post("/control/clear-working")
async def control_clear_working(request: Request):
    """Clear working memory."""
    home = get_agent_home()
    (home / "memory" / "working.md").write_text("# Working Memory\n\n*Cleared via Control Panel*\n")
    return RedirectResponse(url="/control", status_code=303)


@app.post("/control/clear-tasks")
async def control_clear_tasks(request: Request):
    """Clear all pending tasks."""
    home = get_agent_home()
    inbox_path = home / "tasks" / "inbox.md"
    inbox_path.write_text("# Task Inbox\n\n*Cleared via Control Panel*\n")
    return RedirectResponse(url="/control", status_code=303)


@app.post("/control/restore")
async def control_restore(request: Request, snapshot: str = Form(...)):
    """Restore from a snapshot."""
    home = get_agent_home()
    import subprocess
    try:
        # Git checkout the snapshot tag
        subprocess.run(
            ["git", "checkout", snapshot, "--", "."],
            cwd=str(home),
            check=True
        )
    except subprocess.CalledProcessError:
        pass
    return RedirectResponse(url="/control", status_code=303)


# ============================================================================
# API Endpoints (for htmx)
# ============================================================================

@app.get("/api/status")
async def api_status():
    """Get agent status."""
    home = get_agent_home()
    cfg = get_config()
    
    task_mgr = TaskManager(home)
    active = task_mgr.get_active_task()
    pending = task_mgr.get_pending_tasks()
    
    agent = Agent(cfg)
    health = agent.health_check()
    
    # Phase 2: Include budget and cycle info
    budgets = AgentBudgets()
    budget_enforcer = BudgetEnforcer(budgets, home)
    budget_enforcer.load_state()
    
    cycle_count = 0
    if active:
        cycle_history = CycleHistory(home)
        cycle_count = cycle_history.get_cycle_count(active.task_id)
    
    return {
        "active_task": active.task_id if active else None,
        "pending_count": len(pending),
        "health_ok": all(h["ok"] for h in health.values()),
        "cycle_count": cycle_count,
        "budget_status": budget_enforcer.get_status_summary(),
    }


@app.get("/api/cycles/{task_id}")
async def api_cycles(task_id: str):
    """Get cycle data for a task."""
    home = get_agent_home()
    cfg = get_config()
    
    agent = Agent(cfg)
    return agent.get_cycle_status(task_id)


@app.get("/api/curiosity")
async def api_curiosity():
    """Get curiosity statistics."""
    home = get_agent_home()
    cfg = get_config()
    
    agent = Agent(cfg)
    return agent.get_curiosity_stats()


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    get_config()
    print(f"Tooeybot Web UI started - Agent home: {agent_home}")
