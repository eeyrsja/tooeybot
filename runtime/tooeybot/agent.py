"""
Main agent implementation.
"""

import signal
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from .config import Config
from .llm import create_provider, Message, LLMProvider
from .logger import EventLogger
from .executor import Executor
from .context import ContextAssembler
from .tasks import TaskManager, Task

logger = logging.getLogger(__name__)


@dataclass
class TickResult:
    """Result of an agent tick."""
    success: bool
    task_processed: Optional[str] = None
    message: str = ""


class Agent:
    """The main agent runtime."""
    
    def __init__(self, config: Config):
        self.config = config
        self.agent_home = config.agent_home
        self.running = False
        
        # Initialize components
        self.llm: LLMProvider = create_provider(config.llm)
        self.event_logger = EventLogger(self.agent_home)
        self.executor = Executor(
            self.agent_home, 
            self.event_logger,
            timeout=config.execution.command_timeout
        )
        self.context = ContextAssembler(
            self.agent_home,
            max_tokens=config.context.max_tokens - config.context.response_reserve
        )
        self.tasks = TaskManager(self.agent_home)
    
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
        Execute a single agent tick.
        
        This is the core execution loop:
        1. Check for active or pending tasks
        2. If task exists, process it
        3. Otherwise, idle
        """
        logger.info("Starting tick")
        
        # Pre-flight check
        if not self.pre_flight_check():
            return TickResult(
                success=False,
                message="Pre-flight checks failed"
            )
        
        # Check for active task
        task = self.tasks.get_active_task()
        
        # If no active task, get next from inbox
        if not task:
            pending = self.tasks.get_pending_tasks()
            if pending:
                task = pending[0]
                self.tasks.activate_task(task)
                self.event_logger.log_task_update(
                    task.task_id, "activated", "Task moved to active"
                )
        
        if not task:
            logger.info("No pending tasks")
            return TickResult(success=True, message="No pending tasks")
        
        # Process the task
        logger.info(f"Processing task: {task.task_id}")
        return self._process_task(task)
    
    def _process_task(self, task: Task) -> TickResult:
        """Process a single task using LLM reasoning."""
        
        # Build task specification for context
        task_spec = f"""# Current Task: {task.task_id}
Priority: {task.priority}
Deadline: {task.deadline or 'None'}

## Context
{task.context or 'None provided'}

## Description
{task.description}

## Success Criteria
{chr(10).join(f'- {c}' for c in task.success_criteria) if task.success_criteria else 'None specified'}
"""
        
        # Assemble full context
        full_context = self.context.assemble(task_spec=task_spec)
        
        # Build messages for LLM
        system_prompt = """You are Tooeybot, an autonomous agent running in a Linux sandbox.
You process tasks by reasoning about them and executing shell commands.

When you need to execute commands, format them as:
```bash
<command>
```

When you have completed the task, end with:
TASK_COMPLETE: <brief summary>

If you cannot complete the task, end with:
TASK_BLOCKED: <reason>

Always explain your reasoning before executing commands.
Follow your invariants and operating principles at all times."""

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"# Agent Context\n\n{full_context}\n\n---\n\nProcess the current task. What is your plan and what commands will you execute?")
        ]
        
        try:
            response = self.llm.chat(messages, temperature=0.7)
            llm_output = response.content
            
            logger.info(f"LLM response tokens: {response.usage.get('total_tokens', 'unknown')}")
            
        except Exception as e:
            self.event_logger.log_error(
                f"LLM call failed: {e}",
                task_id=task.task_id
            )
            return TickResult(
                success=False,
                task_processed=task.task_id,
                message=f"LLM error: {e}"
            )
        
        # Parse and execute any commands in the response
        # For Phase 0, we use a simple regex to extract bash blocks
        import re
        commands = re.findall(r'```bash\n(.*?)```', llm_output, re.DOTALL)
        
        for cmd_block in commands:
            for line in cmd_block.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    result = self.executor.execute(
                        command="bash",
                        args=["-c", line],
                        task_id=task.task_id,
                        skill="execute_command"
                    )
                    
                    if result.exit_code != 0:
                        logger.warning(f"Command failed: {line}")
                        logger.warning(f"Stderr: {result.stderr}")
        
        # Check for completion markers
        if "TASK_COMPLETE:" in llm_output:
            summary = llm_output.split("TASK_COMPLETE:")[-1].strip().split('\n')[0]
            self.tasks.complete_task(
                task,
                summary=summary,
                approach=llm_output,
                artifacts=[]
            )
            self.event_logger.log_task_update(task.task_id, "completed", summary)
            return TickResult(
                success=True,
                task_processed=task.task_id,
                message=f"Completed: {summary}"
            )
        
        elif "TASK_BLOCKED:" in llm_output:
            reason = llm_output.split("TASK_BLOCKED:")[-1].strip().split('\n')[0]
            self.tasks.block_task(task, reason)
            self.event_logger.log_task_update(task.task_id, "blocked", reason)
            return TickResult(
                success=True,
                task_processed=task.task_id,
                message=f"Blocked: {reason}"
            )
        
        # Task needs more work - keep it active
        return TickResult(
            success=True,
            task_processed=task.task_id,
            message="Task in progress"
        )
    
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
