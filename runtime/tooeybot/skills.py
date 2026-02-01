"""
Skills System - Phase 2

Skills are documented procedures (Markdown) that the LLM reads and follows.
This module handles loading, tracking, drafting, and promoting skills.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Represents a parsed skill from Markdown."""
    name: str
    version: str
    status: str  # core, candidate, learned, deprecated, failed
    path: Path
    purpose: str = ""
    triggers: str = ""
    preconditions: str = ""
    dependencies: List[str] = field(default_factory=list)
    procedure: str = ""
    commands: str = ""
    validation: str = ""
    failure_modes: str = ""
    notes: str = ""
    
    # Runtime tracking
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        """Return full skill identifier like 'core/execute_command@1.0.0'."""
        return f"{self.status}/{self.name}@{self.version}"
    
    def to_context(self) -> str:
        """Format skill for inclusion in LLM context."""
        return f"""## Skill: {self.name} (v{self.version})
**Status**: {self.status}

### Purpose
{self.purpose}

### When to use
{self.triggers}

### Procedure
{self.procedure}

### Failure handling
{self.failure_modes}
"""


class SkillManager:
    """Manages the skills system."""
    
    def __init__(self, agent_home: Path):
        self.agent_home = agent_home
        self.skills_dir = agent_home / "skills"
        self.tracking_file = agent_home / "skills" / ".tracking.json"
        
        # Ensure all skill directories exist
        for subdir in ["core", "candidates", "learned", "deprecated", "failed"]:
            (self.skills_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # Load tracking data
        self.tracking = self._load_tracking()
        
        # Cache of loaded skills
        self._skills_cache: Dict[str, Skill] = {}
    
    def _load_tracking(self) -> Dict[str, Any]:
        """Load skill usage tracking data."""
        if self.tracking_file.exists():
            try:
                return json.loads(self.tracking_file.read_text())
            except:
                pass
        return {"skills": {}}
    
    def _save_tracking(self) -> None:
        """Save skill usage tracking data."""
        self.tracking_file.write_text(json.dumps(self.tracking, indent=2))
    
    def _parse_skill(self, path: Path) -> Optional[Skill]:
        """Parse a skill markdown file into a Skill object."""
        try:
            content = path.read_text()
            
            # Extract skill name from header
            name_match = re.search(r'^# Skill:\s*(.+)$', content, re.MULTILINE)
            name = name_match.group(1).strip() if name_match else path.stem
            
            # Extract version
            version_match = re.search(r'^Version:\s*(.+)$', content, re.MULTILINE)
            version = version_match.group(1).strip() if version_match else "0.0.0"
            
            # Extract status
            status_match = re.search(r'^Status:\s*(.+)$', content, re.MULTILINE)
            status = status_match.group(1).strip() if status_match else "unknown"
            
            # Extract sections
            def extract_section(header: str) -> str:
                pattern = rf'^##\s*{header}\s*\n(.*?)(?=^##|\Z)'
                match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
                return match.group(1).strip() if match else ""
            
            skill = Skill(
                name=name,
                version=version,
                status=status,
                path=path,
                purpose=extract_section("Purpose"),
                triggers=extract_section("Triggers / When to use"),
                preconditions=extract_section("Preconditions"),
                procedure=extract_section("Procedure"),
                commands=extract_section("Commands and tools"),
                validation=extract_section("Validation / Self-test"),
                failure_modes=extract_section("Failure modes & recovery"),
                notes=extract_section("Notes"),
            )
            
            # Extract dependencies
            deps_section = extract_section("Dependencies")
            if deps_section:
                skill.dependencies = [
                    line.strip().lstrip("- ")
                    for line in deps_section.split("\n")
                    if line.strip().startswith("-")
                ]
            
            # Load tracking data
            track_key = f"{status}/{name}"
            if track_key in self.tracking.get("skills", {}):
                track = self.tracking["skills"][track_key]
                skill.use_count = track.get("use_count", 0)
                skill.success_count = track.get("success_count", 0)
                skill.failure_count = track.get("failure_count", 0)
                skill.last_used = track.get("last_used")
            
            return skill
            
        except Exception as e:
            logger.error(f"Failed to parse skill {path}: {e}")
            return None
    
    def load_all_skills(self) -> Dict[str, Skill]:
        """Load all skills from all directories."""
        skills = {}
        
        for status_dir in ["core", "candidates", "learned"]:
            dir_path = self.skills_dir / status_dir
            if dir_path.exists():
                for skill_file in dir_path.glob("*.md"):
                    skill = self._parse_skill(skill_file)
                    if skill:
                        key = f"{status_dir}/{skill.name}"
                        skills[key] = skill
        
        self._skills_cache = skills
        return skills
    
    def get_skill(self, name: str, status: str = None) -> Optional[Skill]:
        """Get a specific skill by name, optionally filtering by status."""
        if not self._skills_cache:
            self.load_all_skills()
        
        if status:
            key = f"{status}/{name}"
            return self._skills_cache.get(key)
        
        # Search in order: learned, core, candidates
        for s in ["learned", "core", "candidates"]:
            key = f"{s}/{name}"
            if key in self._skills_cache:
                return self._skills_cache[key]
        
        return None
    
    def find_relevant_skills(self, task_description: str, limit: int = 3) -> List[Skill]:
        """Find skills relevant to a task based on keyword matching."""
        if not self._skills_cache:
            self.load_all_skills()
        
        task_lower = task_description.lower()
        scored_skills = []
        
        for key, skill in self._skills_cache.items():
            # Skip deprecated/failed
            if skill.status in ["deprecated", "failed"]:
                continue
            
            # Simple keyword scoring
            score = 0
            searchable = f"{skill.name} {skill.purpose} {skill.triggers}".lower()
            
            # Check for keyword matches
            task_words = set(task_lower.split())
            skill_words = set(searchable.split())
            common = task_words & skill_words
            score = len(common)
            
            # Boost for exact name match
            if skill.name.lower() in task_lower:
                score += 5
            
            if score > 0:
                scored_skills.append((score, skill))
        
        # Sort by score descending
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        
        return [skill for _, skill in scored_skills[:limit]]
    
    def record_skill_use(self, skill_name: str, success: bool) -> None:
        """Record that a skill was used."""
        if not self._skills_cache:
            self.load_all_skills()
        
        skill = self.get_skill(skill_name)
        if not skill:
            logger.warning(f"Tried to record use of unknown skill: {skill_name}")
            return
        
        track_key = f"{skill.status}/{skill.name}"
        
        if track_key not in self.tracking.get("skills", {}):
            self.tracking.setdefault("skills", {})[track_key] = {
                "use_count": 0,
                "success_count": 0,
                "failure_count": 0,
            }
        
        track = self.tracking["skills"][track_key]
        track["use_count"] = track.get("use_count", 0) + 1
        track["last_used"] = datetime.now(timezone.utc).isoformat()
        
        if success:
            track["success_count"] = track.get("success_count", 0) + 1
        else:
            track["failure_count"] = track.get("failure_count", 0) + 1
        
        self._save_tracking()
        logger.info(f"Recorded {'success' if success else 'failure'} for skill {skill_name}")
    
    def get_skill_stats(self, skill_name: str) -> Dict[str, Any]:
        """Get usage statistics for a skill."""
        skill = self.get_skill(skill_name)
        if not skill:
            return {}
        
        track_key = f"{skill.status}/{skill.name}"
        track = self.tracking.get("skills", {}).get(track_key, {})
        
        return {
            "name": skill.name,
            "version": skill.version,
            "status": skill.status,
            "use_count": track.get("use_count", 0),
            "success_count": track.get("success_count", 0),
            "failure_count": track.get("failure_count", 0),
            "last_used": track.get("last_used"),
            "ready_for_promotion": (
                skill.status == "candidate" and
                track.get("success_count", 0) >= 3
            )
        }
    
    # =========================================================================
    # Skill Drafting
    # =========================================================================
    
    def draft_skill(
        self,
        name: str,
        purpose: str,
        triggers: str,
        procedure: str,
        commands: str = "",
        dependencies: List[str] = None,
        validation: str = "",
        failure_modes: str = "",
        notes: str = ""
    ) -> Path:
        """Create a new candidate skill."""
        dependencies = dependencies or []
        
        # Generate skill file content
        content = f"""# Skill: {name}

Version: 0.1.0
Status: candidate

## Purpose
{purpose}

## Triggers / When to use
{triggers}

## Preconditions
- Task requires this capability
- Required tools are available

## Dependencies
{chr(10).join(f'- {d}' for d in dependencies) if dependencies else '- None'}

## Procedure
{procedure}

## Commands and tools
{commands if commands else '- Standard bash commands'}

## Validation / Self-test
{validation if validation else '- Test case: (to be defined after first use)'}

## Failure modes & recovery
{failure_modes if failure_modes else '- If command fails → log error and report to task'}

## Notes
{notes if notes else 'Drafted automatically. Needs validation before promotion.'}

## Changelog
- 0.1.0 ({datetime.now().strftime('%Y-%m-%d')}): Initial draft

"""
        # Write to candidates directory
        skill_path = self.skills_dir / "candidates" / f"{name}.md"
        skill_path.write_text(content)
        
        # Update index
        self._update_index()
        
        logger.info(f"Drafted candidate skill: {name}")
        return skill_path
    
    # =========================================================================
    # Skill Promotion
    # =========================================================================
    
    def get_promotable_candidates(self) -> List[Dict[str, Any]]:
        """Get candidate skills that meet promotion criteria."""
        promotable = []
        
        candidates_dir = self.skills_dir / "candidates"
        if not candidates_dir.exists():
            return []
        
        for skill_file in candidates_dir.glob("*.md"):
            skill = self._parse_skill(skill_file)
            if skill:
                stats = self.get_skill_stats(skill.name)
                if stats.get("ready_for_promotion"):
                    promotable.append(stats)
        
        return promotable
    
    def promote_skill(self, name: str) -> Dict[str, Any]:
        """Promote a candidate skill to learned."""
        result = {
            "success": False,
            "skill": name,
            "error": None
        }
        
        # Find the candidate skill
        candidate_path = self.skills_dir / "candidates" / f"{name}.md"
        if not candidate_path.exists():
            result["error"] = f"Candidate skill not found: {name}"
            return result
        
        # Check promotion criteria
        stats = self.get_skill_stats(name)
        if not stats.get("ready_for_promotion"):
            result["error"] = f"Skill not ready for promotion. Needs 3+ successful uses. Current: {stats.get('success_count', 0)}"
            return result
        
        # Read and update the skill content
        content = candidate_path.read_text()
        content = re.sub(r'^Status:\s*candidate', 'Status: learned', content, flags=re.MULTILINE)
        
        # Bump version
        content = re.sub(r'^Version:\s*0\.', 'Version: 1.', content, flags=re.MULTILINE)
        
        # Add promotion note
        promotion_note = f"- Promoted to learned ({datetime.now().strftime('%Y-%m-%d')})"
        content = content.rstrip() + f"\n{promotion_note}\n"
        
        # Move to learned directory
        learned_path = self.skills_dir / "learned" / f"{name}.md"
        learned_path.write_text(content)
        candidate_path.unlink()
        
        # Update tracking
        old_key = f"candidates/{name}"
        new_key = f"learned/{name}"
        if old_key in self.tracking.get("skills", {}):
            self.tracking["skills"][new_key] = self.tracking["skills"].pop(old_key)
            self._save_tracking()
        
        # Update index
        self._update_index()
        
        # Clear cache
        self._skills_cache = {}
        
        result["success"] = True
        logger.info(f"Promoted skill {name} from candidate to learned")
        return result
    
    def deprecate_skill(self, name: str, reason: str = "") -> Dict[str, Any]:
        """Deprecate a learned skill."""
        result = {"success": False, "skill": name, "error": None}
        
        # Find the skill
        skill = self.get_skill(name)
        if not skill:
            result["error"] = f"Skill not found: {name}"
            return result
        
        if skill.status not in ["learned", "candidate"]:
            result["error"] = f"Cannot deprecate {skill.status} skill"
            return result
        
        # Update content
        content = skill.path.read_text()
        content = re.sub(rf'^Status:\s*{skill.status}', 'Status: deprecated', content, flags=re.MULTILINE)
        
        # Add deprecation note
        note = f"- Deprecated ({datetime.now().strftime('%Y-%m-%d')}): {reason}"
        content = content.rstrip() + f"\n{note}\n"
        
        # Move to deprecated directory
        deprecated_path = self.skills_dir / "deprecated" / f"{name}.md"
        deprecated_path.write_text(content)
        skill.path.unlink()
        
        # Update index
        self._update_index()
        
        # Clear cache
        self._skills_cache = {}
        
        result["success"] = True
        return result
    
    # =========================================================================
    # Index Management
    # =========================================================================
    
    def _update_index(self) -> None:
        """Regenerate the skills index."""
        self.load_all_skills()
        
        # Group by status
        by_status = {"core": [], "candidates": [], "learned": [], "deprecated": [], "failed": []}
        
        for key, skill in self._skills_cache.items():
            status = skill.status if skill.status in by_status else "failed"
            by_status[status].append(skill)
        
        # Also check deprecated/failed directories
        for status in ["deprecated", "failed"]:
            dir_path = self.skills_dir / status
            if dir_path.exists():
                for skill_file in dir_path.glob("*.md"):
                    skill = self._parse_skill(skill_file)
                    if skill and skill not in by_status[status]:
                        by_status[status].append(skill)
        
        # Generate index content
        content = """# Skills Index

Catalog of available skills and their status.

---

## How to Use Skills

Skills are documented procedures. When processing a task:
1. The system identifies relevant skills
2. Skill procedures are included in context
3. Follow the procedure to complete the task

---

## Core Skills (immutable)

| Skill | Version | Description |
|-------|---------|-------------|
"""
        for skill in sorted(by_status["core"], key=lambda s: s.name):
            content += f"| [{skill.name}](core/{skill.name}.md) | {skill.version} | {skill.purpose[:50]}... |\n"
        
        content += """
## Learned Skills

| Skill | Version | Uses | Success Rate | Description |
|-------|---------|------|--------------|-------------|
"""
        for skill in sorted(by_status["learned"], key=lambda s: s.name):
            stats = self.get_skill_stats(skill.name)
            uses = stats.get("use_count", 0)
            successes = stats.get("success_count", 0)
            rate = f"{(successes/uses*100):.0f}%" if uses > 0 else "N/A"
            content += f"| [{skill.name}](learned/{skill.name}.md) | {skill.version} | {uses} | {rate} | {skill.purpose[:40]}... |\n"
        
        if not by_status["learned"]:
            content += "| *No learned skills yet* | | | | |\n"
        
        content += """
## Candidate Skills (under validation)

| Skill | Version | Uses | Successes | Ready? |
|-------|---------|------|-----------|--------|
"""
        for skill in sorted(by_status["candidates"], key=lambda s: s.name):
            stats = self.get_skill_stats(skill.name)
            uses = stats.get("use_count", 0)
            successes = stats.get("success_count", 0)
            ready = "✅" if stats.get("ready_for_promotion") else f"Need {3 - successes} more"
            content += f"| [{skill.name}](candidates/{skill.name}.md) | {skill.version} | {uses} | {successes}/3 | {ready} |\n"
        
        if not by_status["candidates"]:
            content += "| *No candidate skills* | | | | |\n"
        
        content += """
## Deprecated Skills

"""
        if by_status["deprecated"]:
            for skill in by_status["deprecated"]:
                content += f"- [{skill.name}](deprecated/{skill.name}.md)\n"
        else:
            content += "*None*\n"
        
        content += f"""
---

*Last updated: {datetime.now(timezone.utc).isoformat()}*
"""
        
        index_path = self.skills_dir / "index.md"
        index_path.write_text(content)
        logger.debug("Updated skills index")
    
    def get_skills_for_context(self, task_description: str = None) -> str:
        """Get formatted skills content for LLM context."""
        if not self._skills_cache:
            self.load_all_skills()
        
        # Always include core skills summary
        core_skills = [s for s in self._skills_cache.values() if s.status == "core"]
        learned_skills = [s for s in self._skills_cache.values() if s.status == "learned"]
        
        content = "# Available Skills\n\n"
        
        # Brief list of all skills
        content += "## Quick Reference\n"
        for skill in core_skills + learned_skills:
            content += f"- **{skill.name}**: {skill.purpose[:60]}\n"
        
        # If task provided, include relevant skill details
        if task_description:
            relevant = self.find_relevant_skills(task_description, limit=2)
            if relevant:
                content += "\n## Relevant Skill Details\n\n"
                for skill in relevant:
                    content += skill.to_context() + "\n---\n"
        
        return content

    # =========================================================================
    # Skill Proposal (from task outcomes)
    # =========================================================================
    
    def propose_skill_from_outcome(
        self,
        task_id: str,
        task_description: str,
        outcome: str,
        success: bool,
        llm_provider=None
    ) -> Optional[Path]:
        """
        Analyze a completed task to see if a reusable skill should be drafted.
        
        Only proposes skills for:
        - Successful tasks (failures don't make good templates)
        - Non-trivial procedures (more than simple commands)
        - Patterns that might be reused
        """
        if not llm_provider or not success:
            return None
        
        from .llm import Message
        
        messages = [
            Message(
                role="system",
                content="""You identify reusable procedures from task outcomes.

A task outcome should become a SKILL when:
1. It involved a multi-step procedure (not just one command)
2. The procedure is likely to be needed again for similar tasks
3. The procedure has clear inputs and outputs
4. It's not already a common/trivial operation

Examples of good skills to draft:
- "Deploy Python App" - multi-step: test, build, deploy, verify
- "Analyze Log Files" - pattern matching, summarization
- "Set Up Development Environment" - install dependencies, configure tools
- "Database Backup and Verify" - dump, compress, checksum, store

Examples of things that are NOT skills:
- Running a single command like "ls" or "cat"
- One-time fixes or cleanups
- Tasks that are too specific to reuse
- Things the shell already does naturally

If the task doesn't represent a reusable procedure, respond: NO_SKILL"""
            ),
            Message(
                role="user",
                content=f"""Task: {task_description}

Agent's approach:
{outcome[:2500]}

Should this become a reusable skill? If yes, provide:
SKILL_NAME: <snake_case_name>
PURPOSE: <one line description>
TRIGGERS: <when should this skill be used>
PROCEDURE:
- Step 1: ...
- Step 2: ...
- Step 3: ...

If not reusable, respond: NO_SKILL"""
            )
        ]
        
        try:
            response = llm_provider.chat(messages)
            
            if "NO_SKILL" in response.content:
                return None
            
            # Parse skill proposal
            name_match = re.search(r'SKILL_NAME:\s*(.+)', response.content)
            purpose_match = re.search(r'PURPOSE:\s*(.+)', response.content)
            triggers_match = re.search(r'TRIGGERS:\s*(.+)', response.content)
            procedure_match = re.search(r'PROCEDURE:\s*\n((?:[-*]\s*.+\n?)+)', response.content)
            
            if not all([name_match, purpose_match, triggers_match, procedure_match]):
                logger.debug("Skill proposal incomplete, skipping")
                return None
            
            name = name_match.group(1).strip().lower().replace(" ", "_").replace("-", "_")
            purpose = purpose_match.group(1).strip()
            triggers = triggers_match.group(1).strip()
            procedure = procedure_match.group(1).strip()
            
            # Check if skill already exists
            existing = self.get_skill(name)
            if existing:
                logger.debug(f"Skill {name} already exists, skipping")
                return None
            
            # Draft the skill
            skill_path = self.draft_skill(
                name=name,
                purpose=purpose,
                triggers=triggers,
                procedure=procedure,
                notes=f"Auto-drafted from task: {task_id}"
            )
            
            logger.info(f"Proposed new skill from task {task_id}: {name}")
            return skill_path
            
        except Exception as e:
            logger.error(f"Failed to propose skill: {e}")
            return None
