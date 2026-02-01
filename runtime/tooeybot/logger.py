"""
Structured event logging.

All events are written as JSONL (one JSON object per line).
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict

from .config import LoggingConfig


@dataclass
class CommandExecution:
    """Details of a command execution."""
    cmd: str
    args: List[str]
    cwd: str
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None


@dataclass
class FileModification:
    """Details of a file modification."""
    path: str
    action: str  # created, modified, deleted
    hash_after: Optional[str] = None


@dataclass
class EventContext:
    """Context for an event."""
    task_id: Optional[str] = None
    triggering_skill: Optional[str] = None
    intent: Optional[str] = None


@dataclass
class EventOutcomes:
    """Outcomes of an event."""
    files_modified: List[FileModification] = None
    artifacts_created: List[str] = None
    observations: Optional[str] = None
    
    def __post_init__(self):
        if self.files_modified is None:
            self.files_modified = []
        if self.artifacts_created is None:
            self.artifacts_created = []


@dataclass 
class EventMetadata:
    """Metadata for an event."""
    llm_model: Optional[str] = None
    context_tokens: Optional[int] = None
    confidence: Optional[float] = None
    curiosity_spend: Optional[float] = None


@dataclass
class Event:
    """A structured event for the JSONL log."""
    event_type: str
    context: Optional[EventContext] = None
    execution: Optional[Dict[str, Any]] = None
    outcomes: Optional[EventOutcomes] = None
    metadata: Optional[EventMetadata] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, removing None values."""
        result = {"timestamp": self.timestamp, "event_type": self.event_type}
        
        if self.context:
            result["context"] = asdict(self.context)
        if self.execution:
            result["execution"] = self.execution
        if self.outcomes:
            result["outcomes"] = asdict(self.outcomes)
        if self.metadata:
            result["metadata"] = asdict(self.metadata)
        
        return result


class EventLogger:
    """Handles structured event logging to JSONL files."""
    
    def __init__(self, agent_home: Path):
        self.agent_home = agent_home
        self.events_dir = agent_home / "logs" / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_today_log(self) -> Path:
        """Get path to today's event log."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.events_dir / f"{today}.jsonl"
    
    def log(self, event: Event) -> None:
        """Write an event to the log."""
        log_path = self._get_today_log()
        
        try:
            with open(log_path, 'a') as f:
                json.dump(event.to_dict(), f, default=str)
                f.write('\n')
        except Exception as e:
            # Logging must never fail silently - at least print to stderr
            print(f"CRITICAL: Failed to write event log: {e}", file=sys.stderr)
            print(f"Event: {event.to_dict()}", file=sys.stderr)
    
    def log_command(
        self,
        cmd: str,
        args: List[str],
        cwd: str,
        exit_code: int,
        duration_ms: int,
        task_id: Optional[str] = None,
        skill: Optional[str] = None
    ) -> None:
        """Convenience method to log a command execution."""
        event = Event(
            event_type="command_execution",
            context=EventContext(
                task_id=task_id,
                triggering_skill=skill
            ),
            execution={
                "commands": [{"cmd": cmd, "args": args, "cwd": cwd}],
                "exit_codes": [exit_code],
                "duration_ms": duration_ms
            }
        )
        self.log(event)
    
    def log_task_update(
        self,
        task_id: str,
        status: str,
        message: str
    ) -> None:
        """Log a task status update."""
        event = Event(
            event_type="task_update",
            context=EventContext(task_id=task_id),
            outcomes=EventOutcomes(observations=f"{status}: {message}")
        )
        self.log(event)
    
    def log_error(
        self,
        error: str,
        task_id: Optional[str] = None,
        context: Optional[str] = None
    ) -> None:
        """Log an error."""
        event = Event(
            event_type="error",
            context=EventContext(task_id=task_id, intent=context),
            outcomes=EventOutcomes(observations=error)
        )
        self.log(event)
    
    def log_startup(self) -> None:
        """Log agent startup."""
        event = Event(
            event_type="startup",
            outcomes=EventOutcomes(observations="Agent started")
        )
        self.log(event)
    
    def log_shutdown(self, reason: str = "normal") -> None:
        """Log agent shutdown."""
        event = Event(
            event_type="shutdown",
            outcomes=EventOutcomes(observations=f"Agent stopped: {reason}")
        )
        self.log(event)
    
    def log_event(
        self,
        event_type: str,
        data: dict,
        level: str = "INFO",
        task_id: Optional[str] = None
    ) -> None:
        """Generic event logging for any event type."""
        event = Event(
            event_type=event_type,
            context=EventContext(task_id=task_id),
            outcomes=EventOutcomes(observations=json.dumps(data))
        )
        self.log(event)


def setup_logging(config: LoggingConfig) -> None:
    """Setup Python's standard logging."""
    level = getattr(logging, config.level.upper(), logging.INFO)
    
    handlers = []
    if config.console:
        handlers.append(logging.StreamHandler(sys.stdout))
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers
    )
