"""
Budget System - Phase 2

Hard constraints on agent behavior to prevent runaway execution.
Budgets are enforced by the runtime, not the LLM.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentBudgets:
    """
    Hard constraints on agent behavior.
    
    These are NOT suggestions - they are enforced limits that
    cause the agent to stop and ask for guidance when exceeded.
    """
    # Per-task limits
    max_iterations_per_task: int = 20
    max_consecutive_failures: int = 3
    max_actions_without_progress: int = 5
    
    # Global task limits
    max_active_tasks: int = 10
    max_tasks_created_per_cycle: int = 3
    max_pending_tasks: int = 50
    
    # Curiosity limits
    curiosity_enabled: bool = True
    max_curiosity_tasks_per_day: int = 5
    max_curiosity_depth: int = 2  # How many levels of curiosity-spawned tasks
    min_curiosity_value_threshold: float = 0.6
    
    # Time limits
    max_task_duration_minutes: int = 30
    
    # Runtime tracking (not configured, tracked at runtime)
    current_task_iterations: int = field(default=0, repr=False)
    current_task_failures: int = field(default=0, repr=False)
    actions_without_progress: int = field(default=0, repr=False)
    curiosity_tasks_today: int = field(default=0, repr=False)
    curiosity_tasks_date: Optional[date] = field(default=None, repr=False)
    task_started_at: Optional[datetime] = field(default=None, repr=False)
    
    def reset_for_new_task(self) -> None:
        """Reset per-task counters."""
        self.current_task_iterations = 0
        self.current_task_failures = 0
        self.actions_without_progress = 0
        self.task_started_at = datetime.now()
    
    def record_iteration(self, made_progress: bool, had_failure: bool) -> None:
        """Record the result of an iteration."""
        self.current_task_iterations += 1
        
        if had_failure:
            self.current_task_failures += 1
        else:
            self.current_task_failures = 0  # Reset on success
        
        if made_progress:
            self.actions_without_progress = 0
        else:
            self.actions_without_progress += 1
    
    def record_curiosity_task(self) -> None:
        """Record creation of a curiosity task."""
        today = date.today()
        if self.curiosity_tasks_date != today:
            self.curiosity_tasks_date = today
            self.curiosity_tasks_today = 0
        self.curiosity_tasks_today += 1
    
    def can_create_curiosity_task(self) -> bool:
        """Check if we can create another curiosity task today."""
        if not self.curiosity_enabled:
            return False
        today = date.today()
        if self.curiosity_tasks_date != today:
            return True
        return self.curiosity_tasks_today < self.max_curiosity_tasks_per_day
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for display/logging."""
        return {
            "limits": {
                "max_iterations_per_task": self.max_iterations_per_task,
                "max_consecutive_failures": self.max_consecutive_failures,
                "max_actions_without_progress": self.max_actions_without_progress,
                "max_active_tasks": self.max_active_tasks,
                "max_curiosity_tasks_per_day": self.max_curiosity_tasks_per_day,
            },
            "current": {
                "task_iterations": self.current_task_iterations,
                "task_failures": self.current_task_failures,
                "actions_without_progress": self.actions_without_progress,
                "curiosity_tasks_today": self.curiosity_tasks_today,
            }
        }


class BudgetEnforcer:
    """
    Enforces hard limits on agent behavior.
    
    Returns clear reasons when limits are exceeded so the agent
    can report meaningfully to the user.
    """
    
    def __init__(self, budgets: AgentBudgets, agent_home: Path):
        self.budgets = budgets
        self.agent_home = agent_home
        self.budget_file = agent_home / "runtime" / "budgets.json"
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
    
    def check_can_continue(self) -> Tuple[bool, str]:
        """
        Check if the agent can continue working on the current task.
        
        Returns:
            (can_continue, reason_if_not)
        """
        b = self.budgets
        
        # Check iteration limit
        if b.current_task_iterations >= b.max_iterations_per_task:
            return False, f"Reached maximum iterations ({b.max_iterations_per_task}) for this task"
        
        # Check consecutive failures
        if b.current_task_failures >= b.max_consecutive_failures:
            return False, f"Too many consecutive failures ({b.current_task_failures})"
        
        # Check no-progress limit
        if b.actions_without_progress >= b.max_actions_without_progress:
            return False, f"No progress for {b.actions_without_progress} consecutive actions"
        
        # Check time limit
        if b.task_started_at:
            elapsed = datetime.now() - b.task_started_at
            if elapsed.total_seconds() / 60 > b.max_task_duration_minutes:
                return False, f"Task exceeded time limit ({b.max_task_duration_minutes} minutes)"
        
        return True, ""
    
    def check_can_create_task(self, pending_count: int, active_count: int) -> Tuple[bool, str]:
        """
        Check if the agent can create a new task.
        
        Returns:
            (can_create, reason_if_not)
        """
        b = self.budgets
        
        if pending_count >= b.max_pending_tasks:
            return False, f"Too many pending tasks ({pending_count}/{b.max_pending_tasks})"
        
        if active_count >= b.max_active_tasks:
            return False, f"Too many active tasks ({active_count}/{b.max_active_tasks})"
        
        return True, ""
    
    def check_can_create_curiosity_task(self, depth: int = 0) -> Tuple[bool, str]:
        """
        Check if the agent can create a curiosity-driven task.
        
        Args:
            depth: How many levels deep in curiosity chain (0 = direct from user task)
        
        Returns:
            (can_create, reason_if_not)
        """
        b = self.budgets
        
        if not b.curiosity_enabled:
            return False, "Curiosity is disabled"
        
        if depth >= b.max_curiosity_depth:
            return False, f"Curiosity depth limit reached ({depth}/{b.max_curiosity_depth})"
        
        if not b.can_create_curiosity_task():
            return False, f"Daily curiosity budget exhausted ({b.curiosity_tasks_today}/{b.max_curiosity_tasks_per_day})"
        
        return True, ""
    
    def save_state(self) -> None:
        """Persist budget state for recovery."""
        state = {
            "timestamp": datetime.now().isoformat(),
            "budgets": self.budgets.to_dict(),
        }
        self.budget_file.write_text(json.dumps(state, indent=2))
    
    def load_state(self) -> None:
        """Load persisted budget state."""
        if not self.budget_file.exists():
            return
        
        try:
            state = json.loads(self.budget_file.read_text())
            current = state.get("budgets", {}).get("current", {})
            
            self.budgets.current_task_iterations = current.get("task_iterations", 0)
            self.budgets.current_task_failures = current.get("task_failures", 0)
            self.budgets.actions_without_progress = current.get("actions_without_progress", 0)
            self.budgets.curiosity_tasks_today = current.get("curiosity_tasks_today", 0)
            
            logger.info(f"Loaded budget state: {current}")
        except Exception as e:
            logger.warning(f"Could not load budget state: {e}")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary for display."""
        b = self.budgets
        return {
            "iterations": f"{b.current_task_iterations}/{b.max_iterations_per_task}",
            "failures": f"{b.current_task_failures}/{b.max_consecutive_failures}",
            "no_progress": f"{b.actions_without_progress}/{b.max_actions_without_progress}",
            "curiosity_today": f"{b.curiosity_tasks_today}/{b.max_curiosity_tasks_per_day}",
            "can_continue": self.check_can_continue()[0],
        }
