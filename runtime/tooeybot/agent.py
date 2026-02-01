"""
Main agent implementation.

Phase 2: Cycle-based reasoning with budgets, reflection, and curiosity.
"""

import signal
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List

from .config import Config
from .llm import create_provider, Message, LLMProvider
from .logger import EventLogger
from .executor import Executor
from .context import ContextAssembler
from .tasks import TaskManager, Task, TaskOrigin
from .skills import SkillManager
from .beliefs import BeliefManager
from .budgets import AgentBudgets, BudgetEnforcer
from .cycle import (
    ReasoningCycle, CycleState, CycleHistory, CycleResult,
    Decision, CuriosityProposal
)
from .reflection import StuckDetector, ReflectionSynthesizer
from .curiosity import CuriosityManager

logger = logging.getLogger(__name__)


@dataclass
class TickResult:
    """Result of an agent tick."""
    success: bool
    task_processed: Optional[str] = None
    message: str = ""
    cycles_run: int = 0
    decision: str = ""
    curiosity_tasks_created: int = 0


class Agent:
    """
    The main agent runtime.
    
    Phase 2 changes:
    - Cycle-based reasoning (PLAN → ACT → OBSERVE → REFLECT → DECIDE)
    - Budget enforcement with hard limits
    - Stuck detection and recovery
    - Curiosity-driven task creation
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.agent_home = config.agent_home
        self.running = False
        
        # Initialize core components
        self.llm: LLMProvider = create_provider(config.llm)
        self.event_logger = EventLogger(self.agent_home)
        self.executor = Executor(
            self.agent_home, 
            self.event_logger,
            timeout=config.execution.command_timeout
        )
        self.skill_manager = SkillManager(self.agent_home)
        self.belief_manager = BeliefManager(self.agent_home)
        self.context = ContextAssembler(
            self.agent_home,
            max_tokens=config.context.max_tokens - config.context.response_reserve,
            skill_manager=self.skill_manager,
            belief_manager=self.belief_manager
        )
        self.tasks = TaskManager(self.agent_home)
        
        # Phase 2 components
        self.budgets = AgentBudgets(
            max_iterations_per_task=config.budgets.max_iterations_per_task,
            max_consecutive_failures=config.budgets.max_consecutive_failures,
            max_actions_without_progress=config.budgets.max_actions_without_progress,
            max_active_tasks=config.budgets.max_active_tasks,
            max_pending_tasks=config.budgets.max_pending_tasks,
            max_task_duration_minutes=config.budgets.max_task_duration_minutes,
            curiosity_enabled=config.curiosity.enabled,
            max_curiosity_tasks_per_day=config.curiosity.max_tasks_per_day,
            max_curiosity_depth=config.curiosity.max_depth,
            min_curiosity_value_threshold=config.curiosity.min_value_threshold,
        )
        self.budget_enforcer = BudgetEnforcer(self.budgets, self.agent_home)
        self.cycle_history = CycleHistory(self.agent_home)
        self.stuck_detector = StuckDetector()
        self.reflection_synthesizer = ReflectionSynthesizer()
        self.curiosity_manager = CuriosityManager(
            self.agent_home,
            self.budgets,
            self.budget_enforcer
        )
    
    def initialize(self) -> None:
        """Initialize the agent filesystem if needed."""
        dirs = [
            self.agent_home / "boot",
            self.agent_home / "memory",
            self.agent_home / "memory" / "archive",
            self.agent_home / "skills" / "core",
            self.agent_home / "skills" / "candidates",
            self.agent_home / "skills" / "learned",
            self.agent_home / "skills" / "deprecated",
            self.agent_home / "skills" / "failed",
            self.agent_home / "logs" / "events",
            self.agent_home / "logs" / "daily",
            self.agent_home / "logs" / "weekly",
            self.agent_home / "logs" / "health",
            self.agent_home / "tasks" / "completed",
            self.agent_home / "tasks" / "blocked",
            self.agent_home / "reflection",
            self.agent_home / "snapshots" / "daily",
            self.agent_home / "snapshots" / "weekly",
            self.agent_home / "snapshots" / "monthly",
            self.agent_home / "scratch",
            self.agent_home / "metrics",
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized agent filesystem at {self.agent_home}")
    
    def health_check(self) -> Dict[str, Dict[str, Any]]:
        """Run health checks and return results."""
        results = {}
        
        # Check agent home exists
        results["agent_home"] = {
            "ok": self.agent_home.exists(),
            "message": f"Agent home: {self.agent_home}"
        }
        
        # Check boot files
        boot_files = ["identity.md", "invariants.md", "operating_principles.md"]
        boot_ok = all((self.agent_home / "boot" / f).exists() for f in boot_files)
        results["boot_files"] = {
            "ok": boot_ok,
            "message": "Boot files present" if boot_ok else "Missing boot files"
        }
        
        # Check logs writable
        try:
            test_path = self.agent_home / "logs" / "events" / ".write_test"
            test_path.write_text("test")
            test_path.unlink()
            results["logs_writable"] = {"ok": True, "message": "Logs directory writable"}
        except Exception as e:
            results["logs_writable"] = {"ok": False, "message": f"Cannot write to logs: {e}"}
        
        # Check LLM connectivity
        llm_ok = self.llm.health_check()
        results["llm_connection"] = {
            "ok": llm_ok,
            "message": f"LLM ({self.config.llm.provider}) " + ("reachable" if llm_ok else "unreachable")
        }
        
        # Check invariants hash
        inv_hash = self.context.get_invariants_hash()
        results["invariants"] = {
            "ok": inv_hash is not None,
            "message": f"Invariants hash: {inv_hash[:16]}..." if inv_hash else "Cannot read invariants"
        }
        
        return results
    
    def pre_flight_check(self) -> bool:
        """Run pre-flight checks before any operation."""
        results = self.health_check()
        
        # Required checks
        required = ["agent_home", "boot_files", "logs_writable"]
        all_ok = all(results.get(k, {}).get("ok", False) for k in required)
        
        if not all_ok:
            logger.error("Pre-flight checks failed")
            for k in required:
                if not results.get(k, {}).get("ok", False):
                    logger.error(f"  - {k}: {results.get(k, {}).get('message', 'unknown')}")
        
        return all_ok
    
    def tick(self) -> TickResult:
        """
        Execute a single agent tick using the cycle-based reasoning loop.
        
        Phase 2 changes:
        - Runs multiple cycles until decision to stop
        - Enforces budget limits
        - Detects stuck patterns
        - Processes curiosity proposals
        
        The loop: PLAN → ACT → OBSERVE → REFLECT → DECIDE → (repeat or stop)
        """
        logger.info("Starting tick (Phase 2 cycle-based)")
        
        # Pre-flight check
        if not self.pre_flight_check():
            return TickResult(
                success=False,
                message="Pre-flight checks failed"
            )
        
        # Load budget state for recovery
        self.budget_enforcer.load_state()
        
        # Check for active task
        task = self.tasks.get_active_task()
        
        # If no active task, get next from inbox
        if not task:
            pending = self.tasks.get_pending_tasks()
            if pending:
                task = pending[0]
                self.tasks.activate_task(task)
                self.budgets.reset_for_new_task()
                self.event_logger.log_task_update(
                    task.task_id, "activated", "Task moved to active"
                )
        
        if not task:
            logger.info("No pending tasks")
            return TickResult(success=True, message="No pending tasks")
        
        # Run cycles until completion or stop condition
        return self._run_cycles(task)
    
    def _run_cycles(self, task: Task) -> TickResult:
        """
        Run reasoning cycles until task completion or stop condition.
        
        This is the core Phase 2 loop that replaces the old _process_task.
        """
        logger.info(f"Starting cycles for task: {task.task_id}")
        
        # Load existing history for this task
        history = self.cycle_history.load_history(task.task_id)
        cycle_num = len(history)
        cycles_run = 0
        curiosity_tasks_created = 0
        
        while True:
            cycle_num += 1
            cycles_run += 1
            
            logger.info(f"Cycle {cycle_num} for task {task.task_id}")
            
            # Budget check
            can_continue, reason = self.budget_enforcer.check_can_continue()
            if not can_continue:
                logger.warning(f"Budget exceeded: {reason}")
                return self._handle_budget_exceeded(task, reason, cycles_run)
            
            # Stuck check
            is_stuck, stuck_reason = self.stuck_detector.is_stuck(history)
            if is_stuck:
                logger.warning(f"Agent stuck: {stuck_reason}")
                return self._handle_stuck(task, stuck_reason, cycles_run)
            
            # Run one cycle
            try:
                cycle = ReasoningCycle(
                    agent=self,
                    task=task,
                    cycle_id=cycle_num,
                    history=history
                )
                result = cycle.run()
            except Exception as e:
                logger.error(f"Cycle failed: {e}")
                self.budgets.record_iteration(made_progress=False, had_failure=True)
                continue
            
            # Persist cycle state
            history.append(result.state)
            self.cycle_history.append_cycle(result.state)
            
            # Update budgets based on reflection
            made_progress = (
                result.state.reflection.progress_made 
                if result.state.reflection else False
            )
            had_failure = (
                not result.state.observation.success 
                if result.state.observation else False
            )
            self.budgets.record_iteration(made_progress, had_failure)
            self.budget_enforcer.save_state()
            
            # Log the cycle
            self.event_logger.log_event(
                "cycle_complete",
                {
                    "task_id": task.task_id,
                    "cycle_id": cycle_num,
                    "decision": result.decision.value,
                    "progress": made_progress,
                },
                level="INFO"
            )
            
            # Process curiosity proposals
            if result.proposed_tasks:
                created = self.curiosity_manager.process_proposals(
                    result.proposed_tasks,
                    parent_task_id=task.task_id,
                    parent_depth=task.curiosity_depth
                )
                curiosity_tasks_created += len(created)
            
            # Act on decision
            if result.decision == Decision.COMPLETE:
                return self._complete_task_with_cycles(
                    task, result, cycles_run, curiosity_tasks_created
                )
            
            elif result.decision == Decision.BLOCKED:
                return self._block_task_with_cycles(
                    task, result, cycles_run, curiosity_tasks_created
                )
            
            elif result.decision == Decision.ASK_USER:
                return self._pause_for_user(
                    task, result, cycles_run, curiosity_tasks_created
                )
            
            elif result.decision == Decision.BUDGET_EXCEEDED:
                return self._handle_budget_exceeded(
                    task, "Budget exceeded", cycles_run
                )
            
            # CONTINUE - loop again
            # Small delay between cycles to be respectful of resources
            time.sleep(0.5)
    
    def _complete_task_with_cycles(
        self, 
        task: Task, 
        result: CycleResult,
        cycles_run: int,
        curiosity_tasks_created: int
    ) -> TickResult:
        """Complete a task after cycle-based processing."""
        summary = result.summary or "Task completed"
        
        # Build approach from cycle history
        history = self.cycle_history.load_history(task.task_id)
        approach_lines = []
        for cycle in history[-10:]:  # Last 10 cycles
            if cycle.action:
                approach_lines.append(
                    f"- Cycle {cycle.cycle_id}: {cycle.action.action_type.value}"
                )
        approach = "\n".join(approach_lines) if approach_lines else "Single cycle completion"
        
        self.tasks.complete_task(
            task,
            summary=summary,
            approach=approach,
            artifacts=[],
            learnings=f"Completed in {cycles_run} cycles. "
                      f"Created {curiosity_tasks_created} curiosity tasks."
        )
        
        self.event_logger.log_task_update(task.task_id, "completed", summary)
        
        return TickResult(
            success=True,
            task_processed=task.task_id,
            message=f"Completed: {summary}",
            cycles_run=cycles_run,
            decision="complete",
            curiosity_tasks_created=curiosity_tasks_created
        )
    
    def _block_task_with_cycles(
        self,
        task: Task,
        result: CycleResult,
        cycles_run: int,
        curiosity_tasks_created: int
    ) -> TickResult:
        """Block a task after cycle-based processing."""
        reason = result.summary or "Task blocked"
        
        self.tasks.block_task(task, reason)
        self.event_logger.log_task_update(task.task_id, "blocked", reason)
        
        return TickResult(
            success=True,
            task_processed=task.task_id,
            message=f"Blocked: {reason}",
            cycles_run=cycles_run,
            decision="blocked",
            curiosity_tasks_created=curiosity_tasks_created
        )
    
    def _pause_for_user(
        self,
        task: Task,
        result: CycleResult,
        cycles_run: int,
        curiosity_tasks_created: int
    ) -> TickResult:
        """Pause task and wait for user input."""
        reason = result.summary or "Needs user clarification"
        
        self.tasks.pause_task(task, reason)
        self.event_logger.log_task_update(task.task_id, "paused", reason)
        
        return TickResult(
            success=True,
            task_processed=task.task_id,
            message=f"Paused for user: {reason}",
            cycles_run=cycles_run,
            decision="ask_user",
            curiosity_tasks_created=curiosity_tasks_created
        )
    
    def _handle_budget_exceeded(
        self,
        task: Task,
        reason: str,
        cycles_run: int
    ) -> TickResult:
        """Handle budget exhaustion."""
        full_reason = f"Budget exceeded: {reason}"
        
        self.tasks.pause_task(task, full_reason)
        self.event_logger.log_task_update(task.task_id, "paused", full_reason)
        self.event_logger.log_event(
            "budget_exceeded",
            {"task_id": task.task_id, "reason": reason},
            level="WARNING"
        )
        
        return TickResult(
            success=True,
            task_processed=task.task_id,
            message=full_reason,
            cycles_run=cycles_run,
            decision="budget_exceeded"
        )
    
    def _handle_stuck(
        self,
        task: Task,
        reason: str,
        cycles_run: int
    ) -> TickResult:
        """Handle stuck detection."""
        full_reason = f"Agent stuck: {reason}"
        
        self.tasks.pause_task(task, full_reason)
        self.event_logger.log_task_update(task.task_id, "paused", full_reason)
        self.event_logger.log_event(
            "stuck_detected",
            {"task_id": task.task_id, "reason": reason},
            level="WARNING"
        )
        
        return TickResult(
            success=True,
            task_processed=task.task_id,
            message=full_reason,
            cycles_run=cycles_run,
            decision="stuck"
        )
    
    def get_cycle_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of cycles for a task."""
        history = self.cycle_history.load_history(task_id)
        budget_status = self.budget_enforcer.get_status_summary()
        
        return {
            "task_id": task_id,
            "cycles": len(history),
            "last_cycle": history[-1].to_dict() if history else None,
            "budgets": budget_status,
            "stuck_indicators": self.stuck_detector.get_stuck_indicators(history),
        }
    
    def get_curiosity_stats(self) -> Dict[str, Any]:
        """Get curiosity system statistics."""
        return self.curiosity_manager.get_daily_stats()
    
    def run(self, interval: int = 60) -> None:
        """Run the agent continuously."""
        self.running = True
        
        # Handle signals for graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Log startup
        self.event_logger.log_startup()
        logger.info("Agent started in continuous mode")
        
        try:
            while self.running:
                result = self.tick()
                
                if result.task_processed:
                    # If we processed a task, immediately check for more
                    continue
                else:
                    # No work, wait before next tick
                    logger.debug(f"Idle, sleeping for {interval}s")
                    time.sleep(interval)
        
        finally:
            self.event_logger.log_shutdown()
            logger.info("Agent stopped")
