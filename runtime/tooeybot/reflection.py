"""
Reflection Engine - Phase 2

Provides structured reflection capabilities including
stuck detection, progress analysis, and curiosity evaluation.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
import logging

from .cycle import CycleState, Reflection, CuriosityProposal, Decision

logger = logging.getLogger(__name__)


class StuckDetector:
    """
    Detects when the agent is making no progress.
    
    Stuck patterns:
    - Repeating the same action multiple times
    - Same error occurring repeatedly
    - No progress for several consecutive cycles
    - Oscillating between states
    """
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
    
    def is_stuck(self, history: List[CycleState]) -> Tuple[bool, str]:
        """
        Analyze recent history for stuck patterns.
        
        Returns:
            (is_stuck, reason)
        """
        if len(history) < self.window_size:
            return False, ""
        
        recent = history[-self.window_size:]
        
        # Check for repeated identical actions
        actions = [
            (c.action.action_type.value, str(c.action.payload))
            for c in recent if c.action
        ]
        if len(actions) >= 3 and len(set(actions[-3:])) == 1:
            return True, f"Repeating same action: {actions[-1][0]}"
        
        # Check for repeated errors
        errors = [
            c.observation.error
            for c in recent
            if c.observation and c.observation.error
        ]
        if len(errors) >= 3:
            # Check if last 3 errors are similar
            last_errors = errors[-3:]
            if self._errors_similar(last_errors):
                return True, f"Same error repeating: {last_errors[-1][:100]}"
        
        # Check for no progress
        no_progress_count = sum(
            1 for c in recent
            if c.reflection and not c.reflection.progress_made
        )
        if no_progress_count >= self.window_size - 1:
            return True, f"No progress for {no_progress_count} consecutive cycles"
        
        # Check for oscillation (A→B→A→B pattern)
        if len(actions) >= 4:
            if (actions[-4] == actions[-2] and 
                actions[-3] == actions[-1] and 
                actions[-4] != actions[-3]):
                return True, "Oscillating between two actions"
        
        return False, ""
    
    def _errors_similar(self, errors: List[str]) -> bool:
        """Check if errors are essentially the same."""
        if not errors:
            return False
        
        # Normalize errors (remove numbers, paths)
        def normalize(e: str) -> str:
            e = re.sub(r'\d+', 'N', e)
            e = re.sub(r'/[^\s]+', '/PATH', e)
            return e.lower()[:100]
        
        normalized = [normalize(e) for e in errors if e]
        return len(set(normalized)) == 1
    
    def get_stuck_indicators(self, history: List[CycleState]) -> List[str]:
        """Get all stuck indicators from recent history."""
        indicators = []
        
        if len(history) < 2:
            return indicators
        
        recent = history[-5:]
        
        # Count consecutive failures
        failures = sum(
            1 for c in recent
            if c.observation and not c.observation.success
        )
        if failures >= 2:
            indicators.append(f"{failures} recent failures")
        
        # Count no-progress cycles
        no_progress = sum(
            1 for c in recent
            if c.reflection and not c.reflection.progress_made
        )
        if no_progress >= 2:
            indicators.append(f"{no_progress} cycles without progress")
        
        # Check confidence trend
        confidences = [
            c.reflection.confidence
            for c in recent
            if c.reflection
        ]
        if len(confidences) >= 3 and all(c < 0.4 for c in confidences[-3:]):
            indicators.append("Low confidence for multiple cycles")
        
        return indicators


class ProgressAnalyzer:
    """Analyzes progress patterns across cycles."""
    
    def analyze_progress(self, history: List[CycleState]) -> Dict[str, Any]:
        """
        Analyze overall progress in task execution.
        
        Returns metrics about how the task is progressing.
        """
        if not history:
            return {"status": "no_history", "cycles": 0}
        
        total = len(history)
        
        # Count successful vs failed actions
        successes = sum(
            1 for c in history
            if c.observation and c.observation.success
        )
        
        # Count cycles with progress
        progress_cycles = sum(
            1 for c in history
            if c.reflection and c.reflection.progress_made
        )
        
        # Calculate average confidence
        confidences = [
            c.reflection.confidence
            for c in history
            if c.reflection
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Trend analysis
        recent_progress = sum(
            1 for c in history[-3:]
            if c.reflection and c.reflection.progress_made
        ) if len(history) >= 3 else progress_cycles
        
        trend = "improving" if recent_progress >= 2 else (
            "stagnating" if recent_progress == 1 else "declining"
        )
        
        return {
            "status": "active",
            "cycles": total,
            "success_rate": successes / total if total > 0 else 0,
            "progress_rate": progress_cycles / total if total > 0 else 0,
            "avg_confidence": avg_confidence,
            "trend": trend,
            "recent_progress": recent_progress,
        }


class CuriosityEvaluator:
    """
    Evaluates and filters curiosity proposals.
    
    Ensures curiosity is productive and bounded.
    """
    
    ALLOWED_CATEGORIES = ["verification", "documentation", "robustness", "exploration"]
    
    def __init__(
        self,
        min_value_threshold: float = 0.6,
        max_proposals_per_cycle: int = 2
    ):
        self.min_value_threshold = min_value_threshold
        self.max_proposals_per_cycle = max_proposals_per_cycle
    
    def evaluate_proposals(
        self,
        proposals: List[CuriosityProposal],
        task_context: str = ""
    ) -> List[CuriosityProposal]:
        """
        Filter and rank curiosity proposals.
        
        Returns only proposals that pass quality checks.
        """
        if not proposals:
            return []
        
        valid = []
        
        for proposal in proposals:
            # Check minimum value
            if proposal.estimated_value < self.min_value_threshold:
                logger.debug(f"Rejecting low-value proposal: {proposal.description[:50]}")
                continue
            
            # Check category is allowed
            if proposal.category not in self.ALLOWED_CATEGORIES:
                logger.debug(f"Rejecting invalid category: {proposal.category}")
                continue
            
            # Check has justification
            if len(proposal.justification) < 10:
                logger.debug(f"Rejecting proposal without justification")
                continue
            
            # Check description is meaningful
            if len(proposal.description) < 20:
                logger.debug(f"Rejecting vague proposal")
                continue
            
            valid.append(proposal)
        
        # Sort by value and take top N
        valid.sort(key=lambda p: p.estimated_value, reverse=True)
        return valid[:self.max_proposals_per_cycle]
    
    def is_duplicate(
        self,
        proposal: CuriosityProposal,
        existing_tasks: List[str]
    ) -> bool:
        """Check if proposal duplicates an existing task."""
        proposal_words = set(proposal.description.lower().split())
        
        for task_desc in existing_tasks:
            task_words = set(task_desc.lower().split())
            overlap = len(proposal_words & task_words)
            if overlap > len(proposal_words) * 0.7:
                return True
        
        return False


class ReflectionSynthesizer:
    """
    Synthesizes reflection data into actionable insights.
    """
    
    def __init__(self):
        self.stuck_detector = StuckDetector()
        self.progress_analyzer = ProgressAnalyzer()
        self.curiosity_evaluator = CuriosityEvaluator()
    
    def synthesize(
        self,
        history: List[CycleState],
        current_reflection: Optional[Reflection] = None
    ) -> Dict[str, Any]:
        """
        Synthesize all reflection data into a summary.
        """
        is_stuck, stuck_reason = self.stuck_detector.is_stuck(history)
        stuck_indicators = self.stuck_detector.get_stuck_indicators(history)
        progress = self.progress_analyzer.analyze_progress(history)
        
        # Get filtered curiosity proposals
        filtered_proposals = []
        if current_reflection and current_reflection.proposed_tasks:
            filtered_proposals = self.curiosity_evaluator.evaluate_proposals(
                current_reflection.proposed_tasks
            )
        
        # Determine recommended decision
        if is_stuck:
            recommended_decision = Decision.ASK_USER
            recommendation_reason = f"Agent appears stuck: {stuck_reason}"
        elif progress.get("trend") == "declining" and progress.get("cycles", 0) > 5:
            recommended_decision = Decision.ASK_USER
            recommendation_reason = "Task progress is declining"
        elif current_reflection and not current_reflection.plan_still_valid:
            recommended_decision = Decision.CONTINUE
            recommendation_reason = "Plan needs revision"
        else:
            recommended_decision = Decision.CONTINUE
            recommendation_reason = "Continue with current approach"
        
        return {
            "is_stuck": is_stuck,
            "stuck_reason": stuck_reason,
            "stuck_indicators": stuck_indicators,
            "progress": progress,
            "filtered_proposals": filtered_proposals,
            "recommended_decision": recommended_decision.value,
            "recommendation_reason": recommendation_reason,
        }
