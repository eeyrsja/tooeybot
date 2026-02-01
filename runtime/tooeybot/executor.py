"""
Shell command executor with safety controls.
"""

import subprocess
import time
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import logging

from .logger import EventLogger

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a command execution."""
    command: str
    args: List[str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


class Executor:
    """Executes shell commands with logging and safety controls."""
    
    def __init__(
        self,
        agent_home: Path,
        event_logger: EventLogger,
        timeout: int = 300
    ):
        self.agent_home = agent_home
        self.event_logger = event_logger
        self.timeout = timeout
        self.scratch_dir = agent_home / "scratch"
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(
        self,
        command: str,
        args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        skill: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a shell command.
        
        All executions are logged to the event log.
        """
        args = args or []
        cwd = cwd or self.scratch_dir
        timeout = timeout or self.timeout
        
        # Build full command
        full_command = [command] + args
        
        logger.info(f"Executing: {' '.join(full_command)} in {cwd}")
        
        start_time = time.monotonic()
        timed_out = False
        
        try:
            result = subprocess.run(
                full_command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
            
        except subprocess.TimeoutExpired as e:
            timed_out = True
            exit_code = -1
            stdout = e.stdout or "" if hasattr(e, 'stdout') else ""
            stderr = f"Command timed out after {timeout}s"
            logger.warning(f"Command timed out: {' '.join(full_command)}")
            
        except FileNotFoundError:
            exit_code = 127
            stdout = ""
            stderr = f"Command not found: {command}"
            logger.error(f"Command not found: {command}")
            
        except Exception as e:
            exit_code = -1
            stdout = ""
            stderr = str(e)
            logger.error(f"Execution error: {e}")
        
        end_time = time.monotonic()
        duration_ms = int((end_time - start_time) * 1000)
        
        # Log the execution
        self.event_logger.log_command(
            cmd=command,
            args=args,
            cwd=str(cwd),
            exit_code=exit_code,
            duration_ms=duration_ms,
            task_id=task_id,
            skill=skill
        )
        
        return ExecutionResult(
            command=command,
            args=args,
            cwd=str(cwd),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out
        )
    
    def execute_script(
        self,
        script: str,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a multi-line bash script.
        
        Writes the script to a temp file and executes it.
        """
        cwd = cwd or self.scratch_dir
        
        # Write script to temp file
        script_path = self.scratch_dir / "_temp_script.sh"
        script_path.write_text(script)
        script_path.chmod(0o755)
        
        try:
            return self.execute(
                command="bash",
                args=[str(script_path)],
                cwd=cwd,
                timeout=timeout,
                task_id=task_id,
                skill="execute_script"
            )
        finally:
            # Cleanup
            if script_path.exists():
                script_path.unlink()
