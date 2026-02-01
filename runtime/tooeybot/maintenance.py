"""
Phase 1 Maintenance: Daily summaries, snapshots, memory promotion, recovery.
"""

import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MaintenanceManager:
    """Handles Phase 1 maintenance tasks."""
    
    def __init__(self, agent_home: Path, llm=None):
        self.agent_home = agent_home
        self.llm = llm
        self.events_dir = agent_home / "logs" / "events"
        self.daily_dir = agent_home / "logs" / "daily"
        self.snapshots_dir = agent_home / "snapshots"
        self.memory_dir = agent_home / "memory"
        
        # Ensure directories exist
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        (self.snapshots_dir / "daily").mkdir(parents=True, exist_ok=True)
        (self.snapshots_dir / "weekly").mkdir(parents=True, exist_ok=True)
    
    # =========================================================================
    # Daily Summaries
    # =========================================================================
    
    def read_events(self, date: str = None) -> List[Dict[str, Any]]:
        """Read events from a specific date's JSONL file."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        log_file = self.events_dir / f"{date}.jsonl"
        events = []
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in {log_file}: {line[:50]}...")
        
        return events
    
    def generate_daily_summary(self, date: str = None) -> str:
        """Generate a daily summary from events."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        events = self.read_events(date)
        
        if not events:
            return f"# Daily Summary: {date}\n\nNo events recorded.\n"
        
        # Categorize events
        tasks_completed = []
        tasks_blocked = []
        commands_run = 0
        errors = []
        
        for event in events:
            event_type = event.get("event_type", "")
            
            if event_type == "task_update":
                obs = event.get("outcomes", {}).get("observations", "")
                task_id = event.get("context", {}).get("task_id", "unknown")
                if "completed" in obs.lower():
                    tasks_completed.append(task_id)
                elif "blocked" in obs.lower():
                    tasks_blocked.append(task_id)
            
            elif event_type == "command_execution":
                commands_run += 1
            
            elif event_type == "error":
                obs = event.get("outcomes", {}).get("observations", "")
                errors.append(obs[:100])
        
        # Build summary
        summary = f"""# Daily Summary: {date}

## Overview
- **Total events**: {len(events)}
- **Commands executed**: {commands_run}
- **Tasks completed**: {len(tasks_completed)}
- **Tasks blocked**: {len(tasks_blocked)}
- **Errors**: {len(errors)}

## Tasks Completed
{chr(10).join(f'- {t}' for t in tasks_completed) if tasks_completed else '- None'}

## Tasks Blocked
{chr(10).join(f'- {t}' for t in tasks_blocked) if tasks_blocked else '- None'}

## Errors
{chr(10).join(f'- {e}' for e in errors) if errors else '- None'}

## Event Timeline
"""
        # Add timeline
        for event in events[:20]:  # Limit to first 20
            ts = event.get("timestamp", "")[:19]
            et = event.get("event_type", "unknown")
            task = event.get("context", {}).get("task_id", "")
            task_str = f" [{task}]" if task else ""
            summary += f"- `{ts}` {et}{task_str}\n"
        
        if len(events) > 20:
            summary += f"\n... and {len(events) - 20} more events\n"
        
        summary += f"\n---\n*Generated: {datetime.now(timezone.utc).isoformat()}*\n"
        
        return summary
    
    def write_daily_summary(self, date: str = None) -> Path:
        """Generate and write daily summary to file."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        summary = self.generate_daily_summary(date)
        output_path = self.daily_dir / f"{date}.md"
        
        output_path.write_text(summary)
        logger.info(f"Wrote daily summary to {output_path}")
        
        return output_path
    
    # =========================================================================
    # Snapshots
    # =========================================================================
    
    def create_snapshot(self, reason: str = "scheduled") -> Dict[str, Any]:
        """Create a git snapshot of the agent directory."""
        result = {
            "success": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "commit": None,
            "tag": None,
            "error": None
        }
        
        try:
            # Check if we're in a git repo
            git_dir = self.agent_home / ".git"
            if not git_dir.exists():
                # Initialize git
                subprocess.run(
                    ["git", "init"],
                    cwd=self.agent_home,
                    capture_output=True,
                    check=True
                )
                logger.info("Initialized git repository")
            
            # Add all files
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.agent_home,
                capture_output=True,
                check=True
            )
            
            # Check if there are changes to commit
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.agent_home,
                capture_output=True,
                text=True
            )
            
            if not status.stdout.strip():
                result["success"] = True
                result["error"] = "No changes to snapshot"
                logger.info("No changes to snapshot")
                return result
            
            # Commit
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
            commit_msg = f"Snapshot: {reason} ({timestamp})"
            
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.agent_home,
                capture_output=True,
                check=True
            )
            
            # Get commit hash
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.agent_home,
                capture_output=True,
                text=True,
                check=True
            )
            result["commit"] = commit_result.stdout.strip()[:12]
            
            # Create tag
            tag_name = f"snapshot-{timestamp}"
            subprocess.run(
                ["git", "tag", tag_name],
                cwd=self.agent_home,
                capture_output=True,
                check=True
            )
            result["tag"] = tag_name
            
            result["success"] = True
            logger.info(f"Created snapshot: {result['commit']} ({tag_name})")
            
        except subprocess.CalledProcessError as e:
            result["error"] = f"Git error: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error(f"Snapshot failed: {result['error']}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Snapshot failed: {e}")
        
        # Write snapshot metadata
        meta_path = self.snapshots_dir / "daily" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(meta_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result
    
    def list_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent snapshots."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{limit}", "--tags"],
                cwd=self.agent_home,
                capture_output=True,
                text=True
            )
            
            snapshots = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(' ', 1)
                    snapshots.append({
                        "commit": parts[0],
                        "message": parts[1] if len(parts) > 1 else ""
                    })
            return snapshots
        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
            return []
    
    # =========================================================================
    # Memory Promotion
    # =========================================================================
    
    def promote_memory(self) -> Dict[str, Any]:
        """Promote important facts from working memory to long-term memory."""
        result = {
            "promoted": [],
            "working_cleared": False
        }
        
        working_path = self.memory_dir / "working.md"
        longterm_path = self.memory_dir / "long_term.md"
        
        if not working_path.exists():
            return result
        
        working_content = working_path.read_text()
        
        # Look for items marked for promotion (e.g., lines with [PROMOTE])
        lines = working_content.split('\n')
        promote_lines = []
        keep_lines = []
        
        for line in lines:
            if '[PROMOTE]' in line or '[IMPORTANT]' in line:
                clean_line = line.replace('[PROMOTE]', '').replace('[IMPORTANT]', '').strip()
                if clean_line:
                    promote_lines.append(clean_line)
            else:
                keep_lines.append(line)
        
        if promote_lines:
            # Append to long-term memory
            longterm_content = longterm_path.read_text() if longterm_path.exists() else "# Long-Term Memory\n\n"
            
            # Add promoted items with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            longterm_content += f"\n## Promoted on {timestamp}\n"
            for item in promote_lines:
                longterm_content += f"- {item}\n"
                result["promoted"].append(item)
            
            longterm_path.write_text(longterm_content)
            
            # Update working memory
            working_path.write_text('\n'.join(keep_lines))
            result["working_cleared"] = True
            
            logger.info(f"Promoted {len(promote_lines)} items to long-term memory")
        
        return result
    
    def update_working_memory(self, content: str, section: str = "Session Notes") -> None:
        """Update a section of working memory."""
        working_path = self.memory_dir / "working.md"
        
        if working_path.exists():
            current = working_path.read_text()
        else:
            current = "# Working Memory\n\n"
        
        # Find and update section or append
        section_header = f"## {section}"
        if section_header in current:
            # Replace section
            parts = current.split(section_header)
            before = parts[0]
            after_parts = parts[1].split('\n## ', 1)
            after = '\n## ' + after_parts[1] if len(after_parts) > 1 else ""
            new_content = f"{before}{section_header}\n{content}\n{after}"
        else:
            # Append section
            new_content = f"{current}\n{section_header}\n{content}\n"
        
        working_path.write_text(new_content)
    
    # =========================================================================
    # Recovery
    # =========================================================================
    
    def restore_snapshot(self, commit_or_tag: str) -> Dict[str, Any]:
        """Restore from a previous snapshot."""
        result = {
            "success": False,
            "restored_to": commit_or_tag,
            "error": None
        }
        
        try:
            # First, create a backup snapshot
            self.create_snapshot(reason=f"pre-restore-backup")
            
            # Reset to the specified commit/tag
            subprocess.run(
                ["git", "checkout", commit_or_tag, "--", "."],
                cwd=self.agent_home,
                capture_output=True,
                check=True
            )
            
            result["success"] = True
            logger.info(f"Restored to {commit_or_tag}")
            
        except subprocess.CalledProcessError as e:
            result["error"] = f"Git error: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error(f"Restore failed: {result['error']}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Restore failed: {e}")
        
        return result
    
    def preflight_check(self) -> Dict[str, bool]:
        """Run pre-flight checks before modifications."""
        checks = {}
        
        # Can read identity
        identity_path = self.agent_home / "boot" / "identity.md"
        checks["read_identity"] = identity_path.exists() and identity_path.read_text().strip() != ""
        
        # Can read invariants
        invariants_path = self.agent_home / "boot" / "invariants.md"
        checks["read_invariants"] = invariants_path.exists() and invariants_path.read_text().strip() != ""
        
        # Can write events
        try:
            test_file = self.events_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            checks["write_events"] = True
        except:
            checks["write_events"] = False
        
        # Can write daily summary
        try:
            test_file = self.daily_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            checks["write_daily"] = True
        except:
            checks["write_daily"] = False
        
        return checks
    
    # =========================================================================
    # Full Maintenance Cycle
    # =========================================================================
    
    def run_daily_maintenance(self) -> Dict[str, Any]:
        """Run all daily maintenance tasks."""
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "preflight": None,
            "summary": None,
            "promotion": None,
            "snapshot": None,
            "success": True
        }
        
        # Pre-flight checks
        results["preflight"] = self.preflight_check()
        if not all(results["preflight"].values()):
            results["success"] = False
            logger.error("Pre-flight checks failed")
            return results
        
        # Generate daily summary
        try:
            summary_path = self.write_daily_summary()
            results["summary"] = {"path": str(summary_path), "success": True}
        except Exception as e:
            results["summary"] = {"error": str(e), "success": False}
            results["success"] = False
        
        # Promote memory
        try:
            results["promotion"] = self.promote_memory()
            results["promotion"]["success"] = True
        except Exception as e:
            results["promotion"] = {"error": str(e), "success": False}
        
        # Create snapshot
        try:
            results["snapshot"] = self.create_snapshot(reason="daily-maintenance")
        except Exception as e:
            results["snapshot"] = {"error": str(e), "success": False}
            results["success"] = False
        
        logger.info(f"Daily maintenance complete: success={results['success']}")
        return results
