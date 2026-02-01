"""
Task parsing and management.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


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


class TaskParser:
    """Parses tasks from the inbox file."""
    
    TASK_PATTERN = re.compile(
        r'---\s*\n'
        r'task_id:\s*(\S+)\s*\n'
        r'priority:\s*(\w+)\s*\n'
        r'(?:deadline:\s*([^\n]+)\s*\n)?'
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
            context = (match.group(4) or "").strip()
            body = match.group(5).strip()
            
            # Parse deadline
            deadline = None
            if deadline_str:
                try:
                    deadline = datetime.fromisoformat(deadline_str.strip())
                except ValueError:
                    logger.warning(f"Could not parse deadline: {deadline_str}")
            
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
                raw_content=match.group(0)
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
