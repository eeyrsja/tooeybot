"""
Task parsing and management.

Phase 2: Added TaskOrigin tracking and enhanced task creation.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TaskOrigin(Enum):
    """Origin of a task - where it came from."""
    USER = "user"           # Created by human user
    PLAN = "plan"           # Created as part of task decomposition
    CURIOSITY = "curiosity" # Created by agent curiosity
    RECOVERY = "recovery"   # Created for error recovery


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    ACTIVE = "active"
    WAITING_USER = "waiting_user"  # Waiting for user response
    PAUSED = "paused"              # Temporarily paused
    COMPLETED = "completed"
    BLOCKED = "blocked"            # Cannot proceed


@dataclass
class Task:
    """A task from the inbox."""
    task_id: str
    priority: str  # high, medium, low
    deadline: Optional[datetime]
    context: str
    description: str
    success_criteria: List[str]
    raw_content: str
    
    # Phase 2 additions
    origin: TaskOrigin = TaskOrigin.USER
    parent_task_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    iteration_count: int = 0
    max_iterations: int = 20
    curiosity_depth: int = 0  # For curiosity-spawned tasks
    status: str = "pending"  # pending, active, waiting_user, paused, completed, blocked
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize task for storage/display."""
        return {
            "task_id": self.task_id,
            "priority": self.priority,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "context": self.context,
            "description": self.description,
            "success_criteria": self.success_criteria,
            "origin": self.origin.value,
            "parent_task_id": self.parent_task_id,
            "created_at": self.created_at.isoformat(),
            "iteration_count": self.iteration_count,
            "curiosity_depth": self.curiosity_depth,
        }


class TaskParser:
    """Parses tasks from the inbox file."""
    
    # Updated pattern to capture origin and parent_task
    TASK_PATTERN = re.compile(
        r'---\s*\n'
        r'task_id:\s*(\S+)\s*\n'
        r'priority:\s*(\w+)\s*\n'
        r'(?:deadline:\s*([^\n]+)\s*\n)?'
        r'(?:origin:\s*(\w+)\s*\n)?'
        r'(?:parent_task:\s*(\S+)\s*\n)?'
        r'(?:curiosity_category:\s*(\w+)\s*\n)?'
        r'(?:curiosity_depth:\s*(\d+)\s*\n)?'
        r'(?:context:\s*\|?\s*\n((?:  [^\n]*\n)*))?'
        r'---\s*\n'
        r'(.*?)(?=\n---|\Z)',
        re.DOTALL | re.MULTILINE
    )
    
    def parse_inbox(self, content: str) -> List[Task]:
        """Parse all tasks from inbox content."""
        tasks = []
        
        matches = self.TASK_PATTERN.finditer(content)
        
        for match in matches:
            task_id = match.group(1)
            priority = match.group(2).lower()
            deadline_str = match.group(3)
            origin_str = match.group(4) or "user"
            parent_task_id = match.group(5)
            # curiosity_category = match.group(6)  # Available if needed
            curiosity_depth_str = match.group(7)
            context = (match.group(8) or "").strip()
            body = match.group(9).strip()
            
            # Parse deadline
            deadline = None
            if deadline_str:
                try:
                    deadline = datetime.fromisoformat(deadline_str.strip())
                except ValueError:
                    logger.warning(f"Could not parse deadline: {deadline_str}")
            
            # Parse origin
            try:
                origin = TaskOrigin(origin_str.lower())
            except ValueError:
                origin = TaskOrigin.USER
            
            # Parse curiosity depth
            curiosity_depth = int(curiosity_depth_str) if curiosity_depth_str else 0
            
            # Extract success criteria
            criteria = []
            criteria_match = re.search(
                r'##\s*Success\s+criteria\s*\n((?:[-*]\s+[^\n]+\n?)+)',
                body,
                re.IGNORECASE
            )
            if criteria_match:
                criteria_text = criteria_match.group(1)
                criteria = [
                    line.strip().lstrip('-*').strip()
                    for line in criteria_text.split('\n')
                    if line.strip()
                ]
            
            # Extract description (everything before success criteria)
            description = body
            if criteria_match:
                description = body[:criteria_match.start()].strip()
            
            # Remove markdown header if present
            description = re.sub(r'^#\s+[^\n]+\n', '', description).strip()
            
            tasks.append(Task(
                task_id=task_id,
                priority=priority,
                deadline=deadline,
                context=context,
                description=description,
                success_criteria=criteria,
                raw_content=match.group(0),
                origin=origin,
                parent_task_id=parent_task_id,
                curiosity_depth=curiosity_depth,
            ))
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        tasks.sort(key=lambda t: (priority_order.get(t.priority, 99), t.deadline or datetime.max))
        
        return tasks


class TaskManager:
    """Manages the task lifecycle."""
    
    def __init__(self, agent_home: Path):
        self.agent_home = agent_home
        self.tasks_dir = agent_home / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        
        self.inbox_path = self.tasks_dir / "inbox.md"
        self.active_path = self.tasks_dir / "active.md"
        self.completed_dir = self.tasks_dir / "completed"
        self.blocked_dir = self.tasks_dir / "blocked"
        
        self.completed_dir.mkdir(exist_ok=True)
        self.blocked_dir.mkdir(exist_ok=True)
        
        self.parser = TaskParser()
    
    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks from inbox."""
        if not self.inbox_path.exists():
            return []
        
        content = self.inbox_path.read_text()
        return self.parser.parse_inbox(content)
    
    def get_active_task(self) -> Optional[Task]:
        """Get the currently active task."""
        if not self.active_path.exists():
            return None
        
        content = self.active_path.read_text()
        if "*No active task*" in content:
            return None
        
        tasks = self.parser.parse_inbox(content)
        return tasks[0] if tasks else None
    
    def activate_task(self, task: Task) -> None:
        """Move a task from inbox to active."""
        # Write to active
        self.active_path.write_text(task.raw_content)
        
        # Remove from inbox
        if self.inbox_path.exists():
            content = self.inbox_path.read_text()
            new_content = content.replace(task.raw_content, "")
            self.inbox_path.write_text(new_content)
        
        logger.info(f"Activated task: {task.task_id}")
    
    def complete_task(
        self,
        task: Task,
        summary: str,
        approach: str,
        artifacts: List[str],
        learnings: Optional[str] = None
    ) -> None:
        """Mark a task as complete and move to completed folder."""
        now = datetime.now().strftime("%Y-%m-%d")
        
        report = f"""# Task: {task.task_id}
Status: ✅ Complete
Completed: {now}

## Summary
{summary}

## Approach
{approach}

## Artifacts
{chr(10).join(f"- {a}" for a in artifacts) if artifacts else "None"}

## Learnings
{learnings or "None noted."}
"""
        
        # Write completion report
        report_path = self.completed_dir / f"{task.task_id}.md"
        report_path.write_text(report)
        
        # Clear active
        self.active_path.write_text("# Active Task\n\n*No active task*\n")
        
        logger.info(f"Completed task: {task.task_id}")
    
    def block_task(self, task: Task, reason: str) -> None:
        """Mark a task as blocked."""
        now = datetime.now().strftime("%Y-%m-%d")
        
        report = f"""# Task: {task.task_id}
Status: ⏸ Blocked
Blocked: {now}

## Reason
{reason}

## Original Task
{task.raw_content}
"""
        
        report_path = self.blocked_dir / f"{task.task_id}.md"
        report_path.write_text(report)
        
        # Clear active
        self.active_path.write_text("# Active Task\n\n*No active task*\n")
        
        logger.info(f"Blocked task: {task.task_id}")
    
    def create_task(
        self,
        description: str,
        origin: TaskOrigin = TaskOrigin.USER,
        priority: str = "medium",
        parent_task_id: Optional[str] = None,
        context: str = "",
        success_criteria: Optional[List[str]] = None,
        task_id: Optional[str] = None,
    ) -> Task:
        """
        Create a new task and add it to the inbox.
        
        This is the primary way to programmatically create tasks.
        """
        if task_id is None:
            task_id = self._generate_task_id(origin)
        
        criteria = success_criteria or ["Task completed successfully"]
        criteria_text = "\n".join(f"- {c}" for c in criteria)
        
        # Build raw content
        origin_line = f"origin: {origin.value}\n" if origin != TaskOrigin.USER else ""
        parent_line = f"parent_task: {parent_task_id}\n" if parent_task_id else ""
        context_block = f"context: |\n  {context}\n" if context else ""
        
        raw_content = f"""---
task_id: {task_id}
priority: {priority}
{origin_line}{parent_line}{context_block}---
{description}

## Success criteria
{criteria_text}
"""
        
        task = Task(
            task_id=task_id,
            priority=priority,
            deadline=None,
            context=context,
            description=description,
            success_criteria=criteria,
            raw_content=raw_content,
            origin=origin,
            parent_task_id=parent_task_id,
        )
        
        # Append to inbox
        current = ""
        if self.inbox_path.exists():
            current = self.inbox_path.read_text()
        self.inbox_path.write_text(current + "\n" + raw_content)
        
        logger.info(f"Created task: {task_id} (origin={origin.value})")
        return task
    
    def _generate_task_id(self, origin: TaskOrigin) -> str:
        """Generate a unique task ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        prefix = origin.value[:3].upper()
        return f"{prefix}-{timestamp}"
    
    def count_by_origin(self) -> Dict[str, int]:
        """Count tasks by origin for analytics."""
        counts = {o.value: 0 for o in TaskOrigin}
        
        for task in self.get_pending_tasks():
            counts[task.origin.value] = counts.get(task.origin.value, 0) + 1
        
        active = self.get_active_task()
        if active:
            counts[active.origin.value] = counts.get(active.origin.value, 0) + 1
        
        return counts
    
    def get_task_tree(self, root_task_id: str) -> Dict[str, Any]:
        """Get a task and all its child tasks (subtasks)."""
        all_tasks = self.get_pending_tasks()
        active = self.get_active_task()
        if active:
            all_tasks.append(active)
        
        def find_children(parent_id: str) -> List[Dict[str, Any]]:
            children = []
            for task in all_tasks:
                if task.parent_task_id == parent_id:
                    children.append({
                        "task": task.to_dict(),
                        "children": find_children(task.task_id),
                    })
            return children
        
        root = None
        for task in all_tasks:
            if task.task_id == root_task_id:
                root = task
                break
        
        if not root:
            return {"error": f"Task {root_task_id} not found"}
        
        return {
            "task": root.to_dict(),
            "children": find_children(root_task_id),
        }
    
    def pause_task(self, task: Task, reason: str) -> None:
        """Pause a task (move back to inbox with pause note)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Add pause note to context
        pause_note = f"Paused at {now}: {reason}"
        updated_context = f"{task.context}\n{pause_note}" if task.context else pause_note
        
        # Update raw content with pause note
        paused_content = task.raw_content.replace(
            "---\n" + task.description,
            f"---\n[PAUSED: {reason}]\n\n{task.description}"
        )
        
        # Add back to inbox
        current = ""
        if self.inbox_path.exists():
            current = self.inbox_path.read_text()
        self.inbox_path.write_text(current + "\n" + paused_content)
        
        # Clear active
        self.active_path.write_text("# Active Task\n\n*No active task*\n")
        
        logger.info(f"Paused task: {task.task_id} - {reason}")
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Find a task by ID from any location."""
        # Check active
        active = self.get_active_task()
        if active and active.task_id == task_id:
            return active
        
        # Check pending
        for task in self.get_pending_tasks():
            if task.task_id == task_id:
                return task
        
        return None
    
    def update_task(self, task: Task) -> None:
        """Update a task's content (typically for status changes)."""
        active = self.get_active_task()
        if active and active.task_id == task.task_id:
            # Rebuild raw content with current state
            self._write_task_to_active(task)
            logger.info(f"Updated task: {task.task_id}")
    
    def _write_task_to_active(self, task: Task) -> None:
        """Write task to active file."""
        content = f"""---
task_id: {task.task_id}
priority: {task.priority}
origin: {task.origin.value if hasattr(task.origin, 'value') else task.origin}
status: {task.status}
"""
        if task.parent_task_id:
            content += f"parent_task: {task.parent_task_id}\n"
        if task.curiosity_depth > 0:
            content += f"curiosity_depth: {task.curiosity_depth}\n"
        if task.context:
            content += f"context: |\n"
            for line in task.context.split('\n'):
                content += f"  {line}\n"
        content += f"""---
{task.description}

### Success Criteria
"""
        for criterion in task.success_criteria:
            content += f"- {criterion}\n"
        
        self.active_path.write_text(content)
        task.raw_content = content
