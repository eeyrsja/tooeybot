"""
Context assembly for LLM calls.

Manages loading and prioritizing context from the agent's filesystem.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """A piece of context to include in LLM calls."""
    name: str
    content: str
    tier: str  # "always", "high", "medium", "low"
    priority: int
    token_estimate: int


class ContextAssembler:
    """Assembles context for LLM calls based on policy."""
    
    # Rough estimate: 1 token ≈ 4 characters
    CHARS_PER_TOKEN = 4
    
    def __init__(self, agent_home: Path, max_tokens: int = 6000):
        self.agent_home = agent_home
        self.max_tokens = max_tokens
        self.boot_dir = agent_home / "boot"
        self.memory_dir = agent_home / "memory"
        self.skills_dir = agent_home / "skills"
        self.logs_dir = agent_home / "logs"
        self.tasks_dir = agent_home / "tasks"
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate."""
        return len(text) // self.CHARS_PER_TOKEN
    
    def read_file_safe(self, path: Path) -> Optional[str]:
        """Read a file, returning None if it doesn't exist."""
        try:
            return path.read_text()
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return None
    
    def get_always_context(self) -> List[ContextItem]:
        """Get context items that are always included."""
        items = []
        
        # Identity - keep this short
        content = self.read_file_safe(self.boot_dir / "identity.md")
        if content:
            items.append(ContextItem(
                name="identity",
                content=content,
                tier="always",
                priority=1,
                token_estimate=self.estimate_tokens(content)
            ))
        
        # Skip invariants and operating_principles for now - they make the LLM over-engineer
        # The runtime handles logging automatically, no need to tell the LLM about I-001
        
        # Skip skills index - it confuses the LLM into using abstract skill names
        
        return items
    
    def get_high_context(self) -> List[ContextItem]:
        """Get high-priority context items."""
        items = []
        
        # Working memory
        content = self.read_file_safe(self.memory_dir / "working.md")
        if content:
            items.append(ContextItem(
                name="working_memory",
                content=content,
                tier="high",
                priority=6,
                token_estimate=self.estimate_tokens(content)
            ))
        
        return items
    
    def get_medium_context(self) -> List[ContextItem]:
        """Get medium-priority context items."""
        items = []
        
        # Long-term memory
        content = self.read_file_safe(self.memory_dir / "long_term.md")
        if content:
            items.append(ContextItem(
                name="long_term_memory",
                content=content,
                tier="medium",
                priority=9,
                token_estimate=self.estimate_tokens(content)
            ))
        
        # Beliefs
        content = self.read_file_safe(self.memory_dir / "beliefs.md")
        if content:
            items.append(ContextItem(
                name="beliefs",
                content=content,
                tier="medium",
                priority=10,
                token_estimate=self.estimate_tokens(content)
            ))
        
        return items
    
    def assemble(
        self,
        task_spec: Optional[str] = None,
        additional_context: Optional[List[ContextItem]] = None
    ) -> str:
        """
        Assemble context for an LLM call.
        
        Returns a formatted string with all context items.
        """
        all_items = []
        
        # Add always-include items
        all_items.extend(self.get_always_context())
        
        # Add task spec if provided
        if task_spec:
            all_items.append(ContextItem(
                name="current_task",
                content=task_spec,
                tier="always",
                priority=4,
                token_estimate=self.estimate_tokens(task_spec)
            ))
        
        # Add high priority
        all_items.extend(self.get_high_context())
        
        # Add medium priority
        all_items.extend(self.get_medium_context())
        
        # Add any additional context
        if additional_context:
            all_items.extend(additional_context)
        
        # Sort by priority
        all_items.sort(key=lambda x: x.priority)
        
        # Assemble within budget
        assembled = []
        total_tokens = 0
        
        for item in all_items:
            if total_tokens + item.token_estimate > self.max_tokens:
                if item.tier == "always":
                    # Always items must be included, truncate if needed
                    available = self.max_tokens - total_tokens
                    if available > 100:  # Only include if meaningful amount
                        truncated = item.content[:available * self.CHARS_PER_TOKEN]
                        assembled.append(f"## {item.name}\n{truncated}\n[truncated]")
                        total_tokens += available
                else:
                    # Skip non-essential items that don't fit
                    logger.debug(f"Skipping {item.name} due to token budget")
                    continue
            else:
                assembled.append(f"## {item.name}\n{item.content}")
                total_tokens += item.token_estimate
        
        logger.info(f"Assembled context: ~{total_tokens} tokens from {len(assembled)} items")
        
        return "\n\n---\n\n".join(assembled)
    
    def get_invariants_hash(self) -> Optional[str]:
        """Get SHA256 hash of invariants file for drift detection."""
        content = self.read_file_safe(self.boot_dir / "invariants.md")
        if content:
            return hashlib.sha256(content.encode()).hexdigest()
        return None
    
    def get_identity_hash(self) -> Optional[str]:
        """Get SHA256 hash of identity file for drift detection."""
        content = self.read_file_safe(self.boot_dir / "identity.md")
        if content:
            return hashlib.sha256(content.encode()).hexdigest()
        return None
