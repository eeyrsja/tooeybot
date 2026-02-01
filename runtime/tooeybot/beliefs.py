"""
Belief System - Phase 3

Manages structured claims with confidence tracking, provenance,
and contradiction detection. Beliefs are actively updated during
task execution based on observations and outcomes.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class Belief:
    """A structured claim with provenance and confidence."""
    belief_id: str  # B-000001 format
    claim: str
    confidence: float  # 0.0 to 1.0
    status: str  # active, contested, deprecated
    belief_type: str  # invariant-derived, observed, inferred, external
    provenance: List[Dict[str, str]]  # [{source: ..., evidence: ...}]
    last_validated: str
    contradictions: List[str]  # List of belief IDs that contradict
    notes: str = ""
    
    def to_markdown(self) -> str:
        """Serialize belief to markdown format."""
        prov_lines = "\n".join(
            f"  - Source: {p.get('source', 'unknown')}" + 
            (f"\n    Evidence: {p.get('evidence')}" if p.get('evidence') else "")
            for p in self.provenance
        )
        
        contradictions = ", ".join(self.contradictions) if self.contradictions else "None"
        
        return f"""## {self.belief_id}
**Claim**: {self.claim}
**Confidence**: {self.confidence}
**Status**: {self.status}
**Type**: {self.belief_type}
**Provenance**:
{prov_lines}
**Last_validated**: {self.last_validated}
**Contradictions**: {contradictions}
**Notes**: {self.notes}
"""

    @classmethod
    def from_markdown(cls, text: str) -> Optional["Belief"]:
        """Parse a belief from markdown block."""
        try:
            # Extract belief ID
            id_match = re.search(r'^## (B-\d+)', text, re.MULTILINE)
            if not id_match:
                return None
            belief_id = id_match.group(1)
            
            # Extract fields
            def extract(pattern: str, default: str = "") -> str:
                match = re.search(pattern, text, re.MULTILINE)
                return match.group(1).strip() if match else default
            
            claim = extract(r'\*\*Claim\*\*:\s*(.+)')
            confidence = float(extract(r'\*\*Confidence\*\*:\s*([\d.]+)', "0.5"))
            status = extract(r'\*\*Status\*\*:\s*(\w+)', "active")
            belief_type = extract(r'\*\*Type\*\*:\s*([\w-]+)', "inferred")
            last_validated = extract(r'\*\*Last_validated\*\*:\s*(.+)', 
                                    datetime.now().strftime("%Y-%m-%d"))
            notes = extract(r'\*\*Notes\*\*:\s*(.+)', "")
            
            # Extract contradictions
            contradictions_str = extract(r'\*\*Contradictions\*\*:\s*(.+)', "None")
            contradictions = []
            if contradictions_str and contradictions_str != "None":
                contradictions = [c.strip() for c in contradictions_str.split(",")]
            
            # Extract provenance (simplified)
            provenance = []
            prov_match = re.search(r'\*\*Provenance\*\*:\s*\n((?:\s+-[^\n]+\n?)+)', text)
            if prov_match:
                for line in prov_match.group(1).split("\n"):
                    if "Source:" in line:
                        source = line.split("Source:")[-1].strip()
                        provenance.append({"source": source})
            
            return cls(
                belief_id=belief_id,
                claim=claim,
                confidence=confidence,
                status=status,
                belief_type=belief_type,
                provenance=provenance,
                last_validated=last_validated,
                contradictions=contradictions,
                notes=notes
            )
        except Exception as e:
            logger.error(f"Failed to parse belief: {e}")
            return None


class BeliefManager:
    """Manages the belief system with active updates."""
    
    def __init__(self, agent_home: Path):
        self.agent_home = agent_home
        self.beliefs_file = agent_home / "memory" / "beliefs.md"
        self._beliefs_cache: Dict[str, Belief] = {}
        self._next_id: int = 1
        self._load_beliefs()
    
    def _load_beliefs(self) -> None:
        """Load all beliefs from beliefs.md."""
        if not self.beliefs_file.exists():
            return
        
        content = self.beliefs_file.read_text()
        
        # Split into belief blocks
        blocks = re.split(r'\n---\n', content)
        
        for block in blocks:
            if block.strip().startswith("## B-"):
                belief = Belief.from_markdown(block)
                if belief:
                    self._beliefs_cache[belief.belief_id] = belief
                    # Track next ID
                    num = int(belief.belief_id.split("-")[1])
                    if num >= self._next_id:
                        self._next_id = num + 1
        
        # Also check for "Next belief ID" marker
        next_match = re.search(r'\*Next belief ID:\s*B-(\d+)\*', content)
        if next_match:
            self._next_id = max(self._next_id, int(next_match.group(1)))
        
        logger.debug(f"Loaded {len(self._beliefs_cache)} beliefs, next ID: B-{self._next_id:06d}")
    
    def _save_beliefs(self) -> None:
        """Save all beliefs to beliefs.md."""
        content = """# Beliefs

Structured claims with provenance and confidence tracking.

---

"""
        # Sort by ID
        for belief_id in sorted(self._beliefs_cache.keys()):
            belief = self._beliefs_cache[belief_id]
            content += belief.to_markdown() + "\n---\n\n"
        
        content += f"*Next belief ID: B-{self._next_id:06d}*\n"
        
        self.beliefs_file.write_text(content)
        logger.debug(f"Saved {len(self._beliefs_cache)} beliefs")
    
    def _generate_id(self) -> str:
        """Generate next belief ID."""
        belief_id = f"B-{self._next_id:06d}"
        self._next_id += 1
        return belief_id
    
    # =========================================================================
    # CRUD Operations
    # =========================================================================
    
    def get_belief(self, belief_id: str) -> Optional[Belief]:
        """Get a belief by ID."""
        return self._beliefs_cache.get(belief_id)
    
    def get_all_beliefs(self, status: str = None) -> List[Belief]:
        """Get all beliefs, optionally filtered by status."""
        beliefs = list(self._beliefs_cache.values())
        if status:
            beliefs = [b for b in beliefs if b.status == status]
        return sorted(beliefs, key=lambda b: b.belief_id)
    
    def add_belief(
        self,
        claim: str,
        confidence: float = 0.7,
        belief_type: str = "inferred",
        source: str = None,
        evidence: str = None,
        notes: str = ""
    ) -> Belief:
        """Add a new belief."""
        belief_id = self._generate_id()
        
        provenance = []
        if source:
            prov = {"source": source}
            if evidence:
                prov["evidence"] = evidence
            provenance.append(prov)
        
        belief = Belief(
            belief_id=belief_id,
            claim=claim,
            confidence=confidence,
            status="active",
            belief_type=belief_type,
            provenance=provenance,
            last_validated=datetime.now().strftime("%Y-%m-%d"),
            contradictions=[],
            notes=notes
        )
        
        self._beliefs_cache[belief_id] = belief
        self._save_beliefs()
        
        logger.info(f"Added belief {belief_id}: {claim[:50]}...")
        return belief
    
    def update_confidence(self, belief_id: str, delta: float, reason: str = "") -> Optional[Belief]:
        """Update confidence on a belief (positive = strengthen, negative = weaken)."""
        belief = self.get_belief(belief_id)
        if not belief:
            return None
        
        old_confidence = belief.confidence
        belief.confidence = max(0.0, min(1.0, belief.confidence + delta))
        belief.last_validated = datetime.now().strftime("%Y-%m-%d")
        
        if reason:
            belief.notes = f"{reason} (was {old_confidence:.2f})"
        
        self._save_beliefs()
        logger.info(f"Updated {belief_id} confidence: {old_confidence:.2f} → {belief.confidence:.2f}")
        return belief
    
    def contest_belief(self, belief_id: str, reason: str, contradicting_id: str = None) -> Optional[Belief]:
        """Mark a belief as contested."""
        belief = self.get_belief(belief_id)
        if not belief:
            return None
        
        belief.status = "contested"
        belief.notes = f"Contested: {reason}"
        
        if contradicting_id:
            if contradicting_id not in belief.contradictions:
                belief.contradictions.append(contradicting_id)
        
        self._save_beliefs()
        logger.info(f"Contested belief {belief_id}")
        return belief
    
    def deprecate_belief(self, belief_id: str, reason: str = "") -> Optional[Belief]:
        """Deprecate a belief."""
        belief = self.get_belief(belief_id)
        if not belief:
            return None
        
        belief.status = "deprecated"
        belief.notes = f"Deprecated: {reason}"
        
        self._save_beliefs()
        logger.info(f"Deprecated belief {belief_id}")
        return belief
    
    # =========================================================================
    # Contradiction Detection
    # =========================================================================
    
    def find_similar_beliefs(self, claim: str, threshold: float = 0.5) -> List[Tuple[Belief, float]]:
        """
        Find beliefs that might be related to a claim.
        Returns list of (belief, similarity_score) tuples.
        
        Uses simple keyword overlap for now.
        """
        claim_words = set(claim.lower().split())
        results = []
        
        for belief in self._beliefs_cache.values():
            if belief.status == "deprecated":
                continue
            
            belief_words = set(belief.claim.lower().split())
            
            # Jaccard similarity
            intersection = len(claim_words & belief_words)
            union = len(claim_words | belief_words)
            
            if union > 0:
                similarity = intersection / union
                if similarity >= threshold:
                    results.append((belief, similarity))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def check_contradiction(self, new_claim: str, llm_provider=None) -> Dict[str, Any]:
        """
        Check if a new claim contradicts existing beliefs.
        
        Returns:
            {
                "has_contradiction": bool,
                "conflicting_beliefs": [Belief, ...],
                "analysis": str  # LLM explanation if provider given
            }
        """
        result = {
            "has_contradiction": False,
            "conflicting_beliefs": [],
            "analysis": ""
        }
        
        # Find similar beliefs first
        similar = self.find_similar_beliefs(new_claim, threshold=0.3)
        
        if not similar:
            return result
        
        # If we have an LLM, ask it to check for contradiction
        if llm_provider:
            beliefs_text = "\n".join(
                f"- {b.belief_id}: {b.claim}" for b, _ in similar[:5]
            )
            
            from .llm import Message
            
            messages = [
                Message(
                    role="system",
                    content="You analyze claims for logical contradictions. Be precise and concise."
                ),
                Message(
                    role="user",
                    content=f"""Does this new claim contradict any of the existing beliefs?

NEW CLAIM: {new_claim}

EXISTING BELIEFS:
{beliefs_text}

Reply in this format:
CONTRADICTS: <belief_id> or NONE
REASON: <brief explanation>"""
                )
            ]
            
            try:
                response = llm_provider.chat(messages)
                result["analysis"] = response.content
                
                # Parse response
                if "CONTRADICTS:" in response.content:
                    match = re.search(r'CONTRADICTS:\s*(B-\d+)', response.content)
                    if match:
                        contradicting_id = match.group(1)
                        belief = self.get_belief(contradicting_id)
                        if belief:
                            result["has_contradiction"] = True
                            result["conflicting_beliefs"] = [belief]
                            
            except Exception as e:
                logger.warning(f"LLM contradiction check failed: {e}")
        
        return result
    
    # =========================================================================
    # Coherence Check
    # =========================================================================
    
    def run_coherence_check(self, llm_provider=None) -> Dict[str, Any]:
        """
        Run a full coherence check on all active beliefs.
        
        Returns summary and writes detailed report to /logs/health/.
        """
        result = {
            "total_beliefs": 0,
            "active": 0,
            "contested": 0,
            "low_confidence": [],  # beliefs with confidence < 0.5
            "potential_contradictions": [],
            "report_path": None
        }
        
        active_beliefs = self.get_all_beliefs(status="active")
        result["total_beliefs"] = len(self._beliefs_cache)
        result["active"] = len(active_beliefs)
        result["contested"] = len(self.get_all_beliefs(status="contested"))
        
        # Find low confidence beliefs
        result["low_confidence"] = [
            b for b in active_beliefs if b.confidence < 0.5
        ]
        
        # Check each pair for contradictions (expensive!)
        if llm_provider and len(active_beliefs) > 1:
            # For now, just check a sample
            for i, belief in enumerate(active_beliefs[:10]):
                check = self.check_contradiction(belief.claim, llm_provider)
                if check["has_contradiction"]:
                    result["potential_contradictions"].append({
                        "belief": belief.belief_id,
                        "conflicts_with": [b.belief_id for b in check["conflicting_beliefs"]],
                        "analysis": check["analysis"]
                    })
        
        # Write report
        report_dir = self.agent_home / "logs" / "health"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        week = datetime.now().strftime("%Y-W%W")
        report_path = report_dir / f"coherence-{week}.md"
        
        report_content = f"""# Coherence Check - {week}

Generated: {datetime.now().isoformat()}

## Summary

- Total beliefs: {result['total_beliefs']}
- Active: {result['active']}
- Contested: {result['contested']}
- Low confidence (<0.5): {len(result['low_confidence'])}
- Potential contradictions: {len(result['potential_contradictions'])}

## Low Confidence Beliefs

"""
        for b in result["low_confidence"]:
            report_content += f"- **{b.belief_id}** ({b.confidence:.2f}): {b.claim}\n"
        
        if not result["low_confidence"]:
            report_content += "*None*\n"
        
        report_content += """
## Potential Contradictions

"""
        for c in result["potential_contradictions"]:
            report_content += f"- **{c['belief']}** conflicts with {c['conflicts_with']}\n"
            report_content += f"  Analysis: {c['analysis'][:200]}...\n\n"
        
        if not result["potential_contradictions"]:
            report_content += "*None detected*\n"
        
        report_content += """
## Recommendations

"""
        if result["low_confidence"]:
            report_content += "- Review and validate low-confidence beliefs\n"
        if result["potential_contradictions"]:
            report_content += "- Resolve contradictions by contesting or deprecating beliefs\n"
        if not result["low_confidence"] and not result["potential_contradictions"]:
            report_content += "- Belief system is coherent ✓\n"
        
        report_path.write_text(report_content)
        result["report_path"] = str(report_path)
        
        logger.info(f"Coherence check complete: {len(result['potential_contradictions'])} issues found")
        return result
    
    # =========================================================================
    # Belief Extraction (from task outcomes)
    # =========================================================================
    
    def extract_beliefs_from_outcome(
        self,
        task_id: str,
        task_description: str,
        outcome: str,
        success: bool,
        llm_provider=None
    ) -> List[Belief]:
        """
        Extract beliefs from a completed task.
        
        The LLM analyzes the outcome and proposes observations
        that could become beliefs.
        """
        if not llm_provider:
            return []
        
        from .llm import Message
        
        messages = [
            Message(
                role="system",
                content="""You extract factual observations from task outcomes.
Only extract concrete, verifiable facts - not opinions or speculation.
Each observation should be a single, clear statement."""
            ),
            Message(
                role="user",
                content=f"""Task: {task_description}
Outcome: {"Success" if success else "Failure"}

Agent's response:
{outcome[:2000]}

Extract 0-3 factual observations from this outcome. Format:
OBSERVATION: <factual claim>
CONFIDENCE: <0.0-1.0>
TYPE: observed | inferred

If nothing worth recording, respond with: NO_OBSERVATIONS"""
            )
        ]
        
        extracted = []
        
        try:
            response = llm_provider.chat(messages)
            
            if "NO_OBSERVATIONS" in response.content:
                return []
            
            # Parse observations
            obs_pattern = r'OBSERVATION:\s*(.+?)\nCONFIDENCE:\s*([\d.]+)\nTYPE:\s*(\w+)'
            matches = re.findall(obs_pattern, response.content, re.MULTILINE)
            
            for claim, conf, obs_type in matches:
                # Check for contradictions first
                contradiction_check = self.check_contradiction(claim, llm_provider)
                
                if contradiction_check["has_contradiction"]:
                    # Don't add contradicting belief, but log it
                    logger.warning(f"Skipping contradicting observation: {claim[:50]}...")
                    continue
                
                belief = self.add_belief(
                    claim=claim.strip(),
                    confidence=float(conf),
                    belief_type=obs_type.strip(),
                    source=f"task:{task_id}",
                    notes=f"Extracted from task outcome"
                )
                extracted.append(belief)
            
        except Exception as e:
            logger.error(f"Failed to extract beliefs: {e}")
        
        return extracted
    
    def get_relevant_beliefs(self, context: str, limit: int = 5) -> List[Belief]:
        """Get beliefs relevant to a given context."""
        similar = self.find_similar_beliefs(context, threshold=0.2)
        return [b for b, _ in similar[:limit]]
    
    def get_beliefs_for_context(self) -> str:
        """Format all active beliefs for LLM context."""
        active = self.get_all_beliefs(status="active")
        
        if not active:
            return "# Beliefs\n\n*No active beliefs recorded.*\n"
        
        content = "# Active Beliefs\n\n"
        for belief in active:
            conf_indicator = "🟢" if belief.confidence >= 0.8 else "🟡" if belief.confidence >= 0.5 else "🔴"
            content += f"- {conf_indicator} **{belief.belief_id}** ({belief.confidence:.1f}): {belief.claim}\n"
        
        return content
