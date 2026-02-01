"""
Reasoning Cycle Engine - Phase 2

Implements the PLAN → ACT → OBSERVE → REFLECT → DECIDE loop.
Each cycle is one complete iteration of agent reasoning.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .agent import Agent
    from .tasks import Task

logger = logging.getLogger(__name__)


class CyclePhase(Enum):
    """Phases of a reasoning cycle."""
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"
    REFLECT = "reflect"
    DECIDE = "decide"


class ActionType(Enum):
    """Types of actions the agent can take."""
    EXECUTE_COMMAND = "execute_command"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    ASK_USER = "ask_user"
    INTERNAL_REASONING = "internal_reasoning"
    COMPLETE_TASK = "complete_task"
    BLOCK_TASK = "block_task"


class Decision(Enum):
    """Decisions after reflection."""
    CONTINUE = "continue"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    ASK_USER = "ask_user"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class Action:
    """
    Exactly ONE action to take.
    
    The agent must choose a single action per cycle.
    This enforces deliberate, traceable behavior.
    """
    action_type: ActionType
    payload: Dict[str, Any]
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "payload": self.payload,
            "reasoning": self.reasoning,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        return cls(
            action_type=ActionType(data["action_type"]),
            payload=data.get("payload", {}),
            reasoning=data.get("reasoning", ""),
        )


@dataclass
class Observation:
    """Result of executing an action."""
    success: bool
    output: str
    error: Optional[str] = None
    files_modified: List[str] = field(default_factory=list)
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output[:2000] if self.output else "",  # Truncate for storage
            "error": self.error,
            "files_modified": self.files_modified,
            "duration_ms": self.duration_ms,
        }


@dataclass
class CuriosityProposal:
    """A proposed new task from curiosity."""
    description: str
    justification: str
    priority: str = "low"
    estimated_value: float = 0.5  # 0-1, how valuable is this exploration
    category: str = "general"  # verification, documentation, robustness, exploration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "justification": self.justification,
            "priority": self.priority,
            "estimated_value": self.estimated_value,
            "category": self.category,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CuriosityProposal":
        return cls(
            description=data.get("description", ""),
            justification=data.get("justification", ""),
            priority=data.get("priority", "low"),
            estimated_value=data.get("estimated_value", 0.5),
            category=data.get("category", "general"),
        )


@dataclass
class Reflection:
    """
    Mandatory reflection after each action.
    
    This is the control point of the system - where the agent
    evaluates progress and proposes additional work.
    """
    progress_made: bool
    what_learned: str
    plan_still_valid: bool
    proposed_tasks: List[CuriosityProposal] = field(default_factory=list)
    stuck_indicators: List[str] = field(default_factory=list)
    confidence: float = 0.5
    next_step_suggestion: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "progress_made": self.progress_made,
            "what_learned": self.what_learned,
            "plan_still_valid": self.plan_still_valid,
            "proposed_tasks": [p.to_dict() for p in self.proposed_tasks],
            "stuck_indicators": self.stuck_indicators,
            "confidence": self.confidence,
            "next_step_suggestion": self.next_step_suggestion,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reflection":
        return cls(
            progress_made=data.get("progress_made", False),
            what_learned=data.get("what_learned", ""),
            plan_still_valid=data.get("plan_still_valid", True),
            proposed_tasks=[CuriosityProposal.from_dict(p) for p in data.get("proposed_tasks", [])],
            stuck_indicators=data.get("stuck_indicators", []),
            confidence=data.get("confidence", 0.5),
            next_step_suggestion=data.get("next_step_suggestion", ""),
        )


@dataclass
class Plan:
    """
    What the agent intends to do.
    
    Created at the start of each cycle to make intent explicit.
    """
    goal: str
    approach: str
    next_action: Action
    remaining_steps: List[str] = field(default_factory=list)
    confidence: float = 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "approach": self.approach,
            "next_action": self.next_action.to_dict(),
            "remaining_steps": self.remaining_steps,
            "confidence": self.confidence,
        }


@dataclass
class CycleState:
    """
    Complete state of a single reasoning cycle.
    
    This is fully serializable for debugging, replay, and recovery.
    """
    cycle_id: int
    task_id: str
    phase: CyclePhase
    plan: Optional[Plan] = None
    action: Optional[Action] = None
    observation: Optional[Observation] = None
    reflection: Optional[Reflection] = None
    decision: Decision = Decision.CONTINUE
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "task_id": self.task_id,
            "phase": self.phase.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "action": self.action.to_dict() if self.action else None,
            "observation": self.observation.to_dict() if self.observation else None,
            "reflection": self.reflection.to_dict() if self.reflection else None,
            "decision": self.decision.value,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CycleState":
        return cls(
            cycle_id=data["cycle_id"],
            task_id=data["task_id"],
            phase=CyclePhase(data["phase"]),
            plan=Plan(**data["plan"]) if data.get("plan") else None,
            action=Action.from_dict(data["action"]) if data.get("action") else None,
            observation=Observation(**data["observation"]) if data.get("observation") else None,
            reflection=Reflection.from_dict(data["reflection"]) if data.get("reflection") else None,
            decision=Decision(data.get("decision", "continue")),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class CycleResult:
    """Result of running a complete cycle."""
    state: CycleState
    decision: Decision
    proposed_tasks: List[CuriosityProposal]
    summary: str = ""


class CycleHistory:
    """Manages cycle history persistence."""
    
    def __init__(self, agent_home: Path):
        self.agent_home = agent_home
        self.history_dir = agent_home / "tasks" / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
    
    def get_history_file(self, task_id: str) -> Path:
        """Get the history file path for a task."""
        return self.history_dir / f"{task_id}.jsonl"
    
    def append_cycle(self, state: CycleState) -> None:
        """Append a cycle state to history."""
        history_file = self.get_history_file(state.task_id)
        with open(history_file, "a") as f:
            f.write(json.dumps(state.to_dict()) + "\n")
    
    def load_history(self, task_id: str) -> List[CycleState]:
        """Load all cycles for a task."""
        history_file = self.get_history_file(task_id)
        if not history_file.exists():
            return []
        
        cycles = []
        for line in history_file.read_text().strip().split("\n"):
            if line.strip():
                try:
                    cycles.append(CycleState.from_dict(json.loads(line)))
                except Exception as e:
                    logger.warning(f"Could not parse cycle: {e}")
        return cycles
    
    def get_last_cycle(self, task_id: str) -> Optional[CycleState]:
        """Get the most recent cycle for a task."""
        history = self.load_history(task_id)
        return history[-1] if history else None
    
    def get_cycle_count(self, task_id: str) -> int:
        """Get the number of cycles for a task."""
        return len(self.load_history(task_id))


class ReasoningCycle:
    """
    Manages a single PLAN → ACT → OBSERVE → REFLECT → DECIDE cycle.
    
    This is the core reasoning engine that replaces the single-shot
    task processing of Phase 1.
    """
    
    # Prompts for each phase
    PLAN_PROMPT = """You are an AUTONOMOUS agent planning the next step to complete a task.

## Current Task
{task_spec}
{task_context}

## Previous Cycles (Recent History)
{history_summary}

## Current Iteration
This is cycle {cycle_num} of maximum {max_cycles}.

## Instructions
1. Review the task, any previous progress, and learnings from history
2. Choose EXACTLY ONE action to take next
3. Be specific and direct
4. Work AUTONOMOUSLY - make reasonable assumptions and proceed

## Available Actions (in order of preference)
- execute_command: Run a shell command (PREFERRED - just do it)
- read_file: Read a file's contents (PREFERRED - gather info yourself)
- write_file: Create or update a file (PREFERRED - just make changes)
- complete_task: Declare the task complete
- block_task: Declare the task blocked (only if truly impossible)
- ask_user: Ask the user for clarification (LAST RESORT ONLY - use sparingly)

## CRITICAL: Autonomy Principle
- You should RARELY need to ask the user anything
- If something is unclear, make a reasonable assumption and proceed
- Only ask_user when you genuinely cannot proceed without user input
- Prefer exploration and experimentation over questions
- If you've asked a question before, the answer should be in the history - DO NOT ask again

## Response Format (JSON only)
{{
    "goal": "What you're trying to achieve",
    "approach": "Brief approach (1-2 sentences)",
    "next_action": {{
        "action_type": "execute_command|read_file|write_file|ask_user|complete_task|block_task",
        "payload": {{
            "command": "...",  // for execute_command
            "path": "...",     // for read_file or write_file
            "content": "...",  // for write_file
            "question": "...", // for ask_user (LAST RESORT)
            "summary": "..."   // for complete_task or block_task
        }},
        "reasoning": "Why this action"
    }},
    "remaining_steps": ["step 1", "step 2"],
    "confidence": 0.8
}}

Respond with ONLY the JSON, no other text."""

    REFLECT_PROMPT = """You just executed an action. Reflect on the result.

## Task
{task_description}
{task_context}

## Action Taken
Type: {action_type}
Payload: {action_payload}
Reasoning: {action_reasoning}

## Result
Success: {success}
Output: {output}
Error: {error}

## Previous Cycles
{history_summary}

## Required Analysis
Analyze what happened and respond in JSON format:

{{
    "progress_made": true/false,
    "what_learned": "What new information did you learn?",
    "plan_still_valid": true/false,
    "stuck_indicators": ["any signs you're stuck"],
    "confidence": 0.0-1.0,
    "next_step_suggestion": "What should happen next",
    "proposed_tasks": []
}}

IMPORTANT:
- Be honest about whether progress was made
- Flag any stuck patterns you notice
- Keep working AUTONOMOUSLY - don't suggest asking users for help
- proposed_tasks should almost always be empty unless there's truly valuable follow-up work

Respond with ONLY the JSON, no other text."""

    DECIDE_PROMPT = """Based on your reflection, decide how to proceed.

## Reflection
Progress made: {progress_made}
What learned: {what_learned}
Plan still valid: {plan_still_valid}
Stuck indicators: {stuck_indicators}
Confidence: {confidence}

## Budget Status
Cycles used: {cycles_used}/{max_cycles}
Failures: {failures}/{max_failures}
No-progress streak: {no_progress}/{max_no_progress}

## Decision Options (in order of preference)
- CONTINUE: More work is needed, proceed to next cycle (DEFAULT - keep working)
- COMPLETE: The task goal has been achieved
- BLOCKED: Cannot proceed - truly impossible without external resources
- ASK_USER: LAST RESORT - only when you absolutely cannot make any progress

## CRITICAL: Autonomy Principle
You are an AUTONOMOUS agent. Your default should be CONTINUE unless the task is done.
- ASK_USER should be extremely rare - only when genuinely stuck with no alternatives
- If you're unsure, make a reasonable assumption and CONTINUE
- Prefer experimentation over asking

Respond with ONLY one word: CONTINUE, COMPLETE, BLOCKED, or ASK_USER"""

    def __init__(
        self, 
        agent: "Agent", 
        task: "Task", 
        cycle_id: int,
        history: List[CycleState]
    ):
        self.agent = agent
        self.task = task
        self.cycle_id = cycle_id
        self.history = history
        self.state = CycleState(
            cycle_id=cycle_id,
            task_id=task.task_id,
            phase=CyclePhase.PLAN,
        )
    
    def run(self) -> CycleResult:
        """Execute one complete cycle."""
        try:
            # PLAN phase
            self.state.phase = CyclePhase.PLAN
            plan = self._plan()
            self.state.plan = plan
            self.state.action = plan.next_action
            
            # Check for immediate completion/block actions
            if plan.next_action.action_type == ActionType.COMPLETE_TASK:
                self.state.decision = Decision.COMPLETE
                return CycleResult(
                    state=self.state,
                    decision=Decision.COMPLETE,
                    proposed_tasks=[],
                    summary=plan.next_action.payload.get("summary", "Task completed"),
                )
            
            if plan.next_action.action_type == ActionType.BLOCK_TASK:
                self.state.decision = Decision.BLOCKED
                return CycleResult(
                    state=self.state,
                    decision=Decision.BLOCKED,
                    proposed_tasks=[],
                    summary=plan.next_action.payload.get("summary", "Task blocked"),
                )
            
            if plan.next_action.action_type == ActionType.ASK_USER:
                self.state.decision = Decision.ASK_USER
                return CycleResult(
                    state=self.state,
                    decision=Decision.ASK_USER,
                    proposed_tasks=[],
                    summary=plan.next_action.payload.get("question", "Need clarification"),
                )
            
            # ACT phase
            self.state.phase = CyclePhase.ACT
            observation = self._act(plan.next_action)
            self.state.observation = observation
            
            # OBSERVE phase (implicit - observation recorded above)
            self.state.phase = CyclePhase.OBSERVE
            
            # REFLECT phase
            self.state.phase = CyclePhase.REFLECT
            reflection = self._reflect(plan.next_action, observation)
            self.state.reflection = reflection
            
            # DECIDE phase
            self.state.phase = CyclePhase.DECIDE
            decision = self._decide(reflection)
            self.state.decision = decision
            
            return CycleResult(
                state=self.state,
                decision=decision,
                proposed_tasks=reflection.proposed_tasks,
                summary=reflection.what_learned,
            )
            
        except Exception as e:
            logger.error(f"Cycle error: {e}")
            self.state.observation = Observation(
                success=False,
                output="",
                error=str(e),
            )
            self.state.decision = Decision.BLOCKED
            return CycleResult(
                state=self.state,
                decision=Decision.BLOCKED,
                proposed_tasks=[],
                summary=f"Cycle failed: {e}",
            )
    
    def _plan(self) -> Plan:
        """Generate a plan with exactly one action."""
        from .llm import Message
        
        # Build task spec
        task_spec = f"""Task ID: {self.task.task_id}
Priority: {self.task.priority}
Description: {self.task.description}

Success Criteria:
{chr(10).join(f'- {c}' for c in self.task.success_criteria) if self.task.success_criteria else '- Complete the task successfully'}
"""
        
        # Build task context (includes user replies, additional info)
        task_context = ""
        if self.task.context:
            task_context = f"\n## Additional Context / User Replies\n{self.task.context}"
        
        # Build history summary
        history_summary = self._build_history_summary()
        
        prompt = self.PLAN_PROMPT.format(
            task_spec=task_spec,
            task_context=task_context,
            history_summary=history_summary,
            cycle_num=self.cycle_id,
            max_cycles=self.agent.budgets.max_iterations_per_task,
        )
        
        messages = [Message(role="user", content=prompt)]
        response = self.agent.llm.chat(messages)
        
        # Parse JSON response
        plan_data = self._parse_json_response(response.content)
        
        action_data = plan_data.get("next_action", {})
        action = Action(
            action_type=ActionType(action_data.get("action_type", "execute_command")),
            payload=action_data.get("payload", {}),
            reasoning=action_data.get("reasoning", ""),
        )
        
        return Plan(
            goal=plan_data.get("goal", "Complete the task"),
            approach=plan_data.get("approach", ""),
            next_action=action,
            remaining_steps=plan_data.get("remaining_steps", []),
            confidence=plan_data.get("confidence", 0.7),
        )
    
    def _act(self, action: Action) -> Observation:
        """Execute the planned action."""
        import time
        start = time.monotonic()
        
        try:
            if action.action_type == ActionType.EXECUTE_COMMAND:
                result = self.agent.executor.execute(
                    command="bash",
                    args=["-c", action.payload.get("command", "echo 'No command'")],
                    task_id=self.task.task_id,
                )
                return Observation(
                    success=result.exit_code == 0,
                    output=result.stdout,
                    error=result.stderr if result.exit_code != 0 else None,
                    duration_ms=result.duration_ms,
                )
            
            elif action.action_type == ActionType.READ_FILE:
                path = Path(action.payload.get("path", ""))
                if path.exists():
                    content = path.read_text()
                    return Observation(
                        success=True,
                        output=content[:5000],  # Limit output size
                        duration_ms=int((time.monotonic() - start) * 1000),
                    )
                else:
                    return Observation(
                        success=False,
                        output="",
                        error=f"File not found: {path}",
                        duration_ms=int((time.monotonic() - start) * 1000),
                    )
            
            elif action.action_type == ActionType.WRITE_FILE:
                path = Path(action.payload.get("path", ""))
                content = action.payload.get("content", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                return Observation(
                    success=True,
                    output=f"Wrote {len(content)} bytes to {path}",
                    files_modified=[str(path)],
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            
            elif action.action_type == ActionType.INTERNAL_REASONING:
                # No external action, just record the reasoning
                return Observation(
                    success=True,
                    output=action.payload.get("reasoning", "Internal reasoning step"),
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            
            else:
                return Observation(
                    success=False,
                    output="",
                    error=f"Unknown action type: {action.action_type}",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                
        except Exception as e:
            return Observation(
                success=False,
                output="",
                error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
    
    def _reflect(self, action: Action, observation: Observation) -> Reflection:
        """Generate structured reflection."""
        from .llm import Message
        
        history_summary = self._build_history_summary()
        
        # Build task context (includes user replies)
        task_context = ""
        if self.task.context:
            task_context = f"\n## User Replies / Context\n{self.task.context}"
        
        prompt = self.REFLECT_PROMPT.format(
            task_description=self.task.description,
            task_context=task_context,
            action_type=action.action_type.value,
            action_payload=json.dumps(action.payload),
            action_reasoning=action.reasoning,
            success=observation.success,
            output=observation.output[:1000] if observation.output else "(no output)",
            error=observation.error or "(no error)",
            history_summary=history_summary,
        )
        
        messages = [Message(role="user", content=prompt)]
        response = self.agent.llm.chat(messages)
        
        # Parse JSON response
        reflect_data = self._parse_json_response(response.content)
        
        proposed = [
            CuriosityProposal.from_dict(p) 
            for p in reflect_data.get("proposed_tasks", [])
        ]
        
        return Reflection(
            progress_made=reflect_data.get("progress_made", False),
            what_learned=reflect_data.get("what_learned", ""),
            plan_still_valid=reflect_data.get("plan_still_valid", True),
            proposed_tasks=proposed,
            stuck_indicators=reflect_data.get("stuck_indicators", []),
            confidence=reflect_data.get("confidence", 0.5),
            next_step_suggestion=reflect_data.get("next_step_suggestion", ""),
        )
    
    def _decide(self, reflection: Reflection) -> Decision:
        """Decide how to proceed based on reflection."""
        from .llm import Message
        
        budgets = self.agent.budgets
        
        prompt = self.DECIDE_PROMPT.format(
            progress_made=reflection.progress_made,
            what_learned=reflection.what_learned,
            plan_still_valid=reflection.plan_still_valid,
            stuck_indicators=reflection.stuck_indicators,
            confidence=reflection.confidence,
            cycles_used=budgets.current_task_iterations,
            max_cycles=budgets.max_iterations_per_task,
            failures=budgets.current_task_failures,
            max_failures=budgets.max_consecutive_failures,
            no_progress=budgets.actions_without_progress,
            max_no_progress=budgets.max_actions_without_progress,
        )
        
        messages = [Message(role="user", content=prompt)]
        response = self.agent.llm.chat(messages)
        
        decision_text = response.content.strip().upper()
        
        if "COMPLETE" in decision_text:
            return Decision.COMPLETE
        elif "BLOCKED" in decision_text:
            return Decision.BLOCKED
        elif "ASK_USER" in decision_text:
            return Decision.ASK_USER
        else:
            return Decision.CONTINUE
    
    def _build_history_summary(self) -> str:
        """Build a rich summary of previous cycles including outputs and learnings."""
        if not self.history:
            return "No previous cycles. This is a fresh start."
        
        summary_lines = []
        for cycle in self.history[-5:]:  # Last 5 cycles
            action_type = cycle.action.action_type.value if cycle.action else "unknown"
            
            # Start with cycle header
            lines = [f"### Cycle {cycle.cycle_id}: {action_type}"]
            
            # Include action details
            if cycle.action:
                payload = cycle.action.payload
                if action_type == "execute_command":
                    lines.append(f"Command: `{payload.get('command', 'N/A')}`")
                elif action_type == "read_file":
                    lines.append(f"File: `{payload.get('path', 'N/A')}`")
                elif action_type == "write_file":
                    lines.append(f"Wrote to: `{payload.get('path', 'N/A')}`")
                elif action_type == "ask_user":
                    lines.append(f"Question: {payload.get('question', 'N/A')}")
                if cycle.action.reasoning:
                    lines.append(f"Reasoning: {cycle.action.reasoning}")
            
            # Include observation (truncated)
            if cycle.observation:
                success = "✓" if cycle.observation.success else "✗"
                lines.append(f"Result: {success}")
                if cycle.observation.output:
                    output = cycle.observation.output[:500]
                    if len(cycle.observation.output) > 500:
                        output += "...(truncated)"
                    lines.append(f"Output: {output}")
                if cycle.observation.error:
                    lines.append(f"Error: {cycle.observation.error}")
            
            # Include what was learned
            if cycle.reflection:
                if cycle.reflection.what_learned:
                    lines.append(f"Learned: {cycle.reflection.what_learned}")
                if not cycle.reflection.progress_made:
                    lines.append("(No progress this cycle)")
            
            summary_lines.append("\n".join(lines))
        
        return "\n\n".join(summary_lines)
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Try to extract JSON from code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        # Clean up common issues
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse JSON: {e}")
            logger.debug(f"Content was: {content[:500]}")
            # Return minimal valid structure
            return {
                "goal": "Continue task",
                "approach": "Proceed with available information",
                "next_action": {
                    "action_type": "execute_command",
                    "payload": {"command": "echo 'Parse error, continuing'"},
                    "reasoning": "JSON parse failed, using fallback"
                },
                "progress_made": False,
                "what_learned": "Response parsing failed",
                "plan_still_valid": True,
            }
