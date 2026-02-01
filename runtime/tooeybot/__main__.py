"""
Tooeybot CLI entry point.
"""

import argparse
import sys
from pathlib import Path

from .config import load_config
from .agent import Agent
from .logger import setup_logging
from .maintenance import MaintenanceManager
from .skills import SkillManager


def main():
    parser = argparse.ArgumentParser(
        prog="tooeybot",
        description="Tooeybot - Autonomous Agent Runtime"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.yaml"),
        help="Path to configuration file"
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # tick command - single execution cycle
    tick_parser = subparsers.add_parser("tick", help="Run a single agent tick")
    
    # run command - continuous execution
    run_parser = subparsers.add_parser("run", help="Run agent continuously")
    run_parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="Seconds between ticks when idle"
    )
    
    # health command - check system health
    health_parser = subparsers.add_parser("health", help="Run health checks")
    
    # init command - initialize agent filesystem
    init_parser = subparsers.add_parser("init", help="Initialize agent filesystem")
    
    # --- Phase 1 Commands ---
    
    # summarize command - generate daily summary
    summarize_parser = subparsers.add_parser("summarize", help="Generate daily summary from events")
    summarize_parser.add_argument(
        "--date", "-d",
        type=str,
        default=None,
        help="Date to summarize (YYYY-MM-DD), defaults to today"
    )
    
    # snapshot command - create git snapshot
    snapshot_parser = subparsers.add_parser("snapshot", help="Create a git snapshot")
    snapshot_parser.add_argument(
        "--reason", "-r",
        type=str,
        default="manual",
        help="Reason for snapshot"
    )
    
    # restore command - restore from snapshot
    restore_parser = subparsers.add_parser("restore", help="Restore from a snapshot")
    restore_parser.add_argument(
        "target",
        type=str,
        help="Commit hash or tag to restore to"
    )
    
    # maintain command - run daily maintenance
    maintain_parser = subparsers.add_parser("maintain", help="Run daily maintenance tasks")
    
    # recall command - search memories and summaries
    recall_parser = subparsers.add_parser("recall", help="Recall from memory/summaries")
    recall_parser.add_argument(
        "query",
        type=str,
        help="What to search for"
    )
    recall_parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="How many days back to search"
    )
    
    # --- Phase 2: Skills Commands ---
    
    # skill-list command - list all skills
    skill_list_parser = subparsers.add_parser("skill-list", help="List all skills")
    skill_list_parser.add_argument(
        "--status", "-s",
        type=str,
        choices=["core", "learned", "candidate", "all"],
        default="all",
        help="Filter by status"
    )
    
    # skill-stats command - show skill statistics
    skill_stats_parser = subparsers.add_parser("skill-stats", help="Show skill statistics")
    skill_stats_parser.add_argument(
        "name",
        type=str,
        help="Skill name"
    )
    
    # skill-promote command - promote a candidate skill
    skill_promote_parser = subparsers.add_parser("skill-promote", help="Promote a candidate skill")
    skill_promote_parser.add_argument(
        "name",
        type=str,
        help="Skill name to promote"
    )
    
    # skill-draft command - draft a new skill
    skill_draft_parser = subparsers.add_parser("skill-draft", help="Draft a new skill")
    skill_draft_parser.add_argument(
        "name",
        type=str,
        help="Skill name"
    )
    skill_draft_parser.add_argument(
        "--purpose", "-p",
        type=str,
        required=True,
        help="What the skill does"
    )
    skill_draft_parser.add_argument(
        "--triggers", "-t",
        type=str,
        required=True,
        help="When to use the skill"
    )
    skill_draft_parser.add_argument(
        "--procedure",
        type=str,
        required=True,
        help="Step-by-step procedure"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Configuration file not found: {args.config}", file=sys.stderr)
        print("Copy config.example.yaml to config.yaml and adjust settings.", file=sys.stderr)
        sys.exit(1)
    
    # Setup logging
    setup_logging(config.logging)
    
    # Create agent
    agent = Agent(config)
    
    # Execute command
    if args.command == "tick":
        result = agent.tick()
        sys.exit(0 if result.success else 1)
    
    elif args.command == "run":
        agent.run(interval=args.interval)
    
    elif args.command == "health":
        result = agent.health_check()
        for check, status in result.items():
            icon = "✅" if status["ok"] else "❌"
            print(f"{icon} {check}: {status['message']}")
        sys.exit(0 if all(s["ok"] for s in result.values()) else 1)
    
    elif args.command == "init":
        agent.initialize()
        print("Agent filesystem initialized.")
    
    # --- Phase 1 Commands ---
    
    elif args.command == "summarize":
        maintenance = MaintenanceManager(config.agent_home)
        summary_path = maintenance.write_daily_summary(args.date)
        print(f"✅ Summary written to: {summary_path}")
        print("\n" + maintenance.generate_daily_summary(args.date))
    
    elif args.command == "snapshot":
        maintenance = MaintenanceManager(config.agent_home)
        result = maintenance.create_snapshot(reason=args.reason)
        if result["success"]:
            print(f"✅ Snapshot created: {result['commit']} ({result['tag']})")
        else:
            print(f"❌ Snapshot failed: {result['error']}")
            sys.exit(1)
    
    elif args.command == "restore":
        maintenance = MaintenanceManager(config.agent_home)
        print(f"⚠️  Restoring to: {args.target}")
        result = maintenance.restore_snapshot(args.target)
        if result["success"]:
            print(f"✅ Restored to: {args.target}")
        else:
            print(f"❌ Restore failed: {result['error']}")
            sys.exit(1)
    
    elif args.command == "maintain":
        maintenance = MaintenanceManager(config.agent_home)
        print("Running daily maintenance...")
        result = maintenance.run_daily_maintenance()
        
        print(f"\n📋 Pre-flight checks:")
        for check, ok in result["preflight"].items():
            print(f"   {'✅' if ok else '❌'} {check}")
        
        print(f"\n📝 Summary: {result['summary'].get('path', result['summary'].get('error', 'N/A'))}")
        
        if result["promotion"].get("promoted"):
            print(f"\n📤 Promoted {len(result['promotion']['promoted'])} items to long-term memory")
        
        if result["snapshot"].get("success"):
            print(f"\n📸 Snapshot: {result['snapshot'].get('commit', 'N/A')}")
        
        print(f"\n{'✅ Maintenance complete' if result['success'] else '❌ Maintenance had errors'}")
        sys.exit(0 if result["success"] else 1)
    
    elif args.command == "recall":
        from datetime import datetime, timedelta
        maintenance = MaintenanceManager(config.agent_home)
        
        print(f"🔍 Searching for: {args.query}")
        print(f"   Looking back {args.days} days...\n")
        
        found = []
        today = datetime.now()
        
        for i in range(args.days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            summary_path = config.agent_home / "logs" / "daily" / f"{date}.md"
            
            if summary_path.exists():
                content = summary_path.read_text()
                if args.query.lower() in content.lower():
                    found.append((date, summary_path))
                    print(f"📅 {date}: Found in daily summary")
        
        # Also search long-term memory
        longterm_path = config.agent_home / "memory" / "long_term.md"
        if longterm_path.exists():
            content = longterm_path.read_text()
            if args.query.lower() in content.lower():
                print(f"📚 Found in long-term memory")
        
        if not found:
            print("No matches found in recent summaries.")
    
    # --- Phase 2: Skills Commands ---
    
    elif args.command == "skill-list":
        skills_mgr = SkillManager(config.agent_home)
        skills = skills_mgr.load_all_skills()
        
        # Filter by status
        if args.status != "all":
            skills = {k: v for k, v in skills.items() if v.status == args.status}
        
        if not skills:
            print(f"No skills found with status: {args.status}")
            sys.exit(0)
        
        # Group by status
        by_status = {}
        for key, skill in skills.items():
            by_status.setdefault(skill.status, []).append(skill)
        
        for status, skill_list in by_status.items():
            print(f"\n📁 {status.upper()} SKILLS:")
            for skill in sorted(skill_list, key=lambda s: s.name):
                stats = skills_mgr.get_skill_stats(skill.name)
                uses = stats.get("use_count", 0)
                successes = stats.get("success_count", 0)
                print(f"   • {skill.name} v{skill.version} (uses: {uses}, success: {successes})")
                print(f"     {skill.purpose[:60]}...")
    
    elif args.command == "skill-stats":
        skills_mgr = SkillManager(config.agent_home)
        stats = skills_mgr.get_skill_stats(args.name)
        
        if not stats:
            print(f"❌ Skill not found: {args.name}")
            sys.exit(1)
        
        print(f"📊 Skill: {stats['name']}")
        print(f"   Version: {stats['version']}")
        print(f"   Status:  {stats['status']}")
        print(f"   Uses:    {stats['use_count']}")
        print(f"   Success: {stats['success_count']}")
        print(f"   Failure: {stats['failure_count']}")
        if stats.get("last_used"):
            print(f"   Last used: {stats['last_used']}")
        if stats.get("ready_for_promotion"):
            print(f"   ✅ Ready for promotion!")
    
    elif args.command == "skill-promote":
        skills_mgr = SkillManager(config.agent_home)
        
        # Show promotable candidates first
        promotable = skills_mgr.get_promotable_candidates()
        if promotable:
            print("📋 Candidates ready for promotion:")
            for p in promotable:
                print(f"   • {p['name']} ({p['success_count']} successful uses)")
        
        # Attempt promotion
        result = skills_mgr.promote_skill(args.name)
        
        if result["success"]:
            print(f"\n✅ Promoted {args.name} to learned skills!")
        else:
            print(f"\n❌ Promotion failed: {result['error']}")
            sys.exit(1)
    
    elif args.command == "skill-draft":
        skills_mgr = SkillManager(config.agent_home)
        
        skill_path = skills_mgr.draft_skill(
            name=args.name,
            purpose=args.purpose,
            triggers=args.triggers,
            procedure=args.procedure
        )
        
        print(f"✅ Drafted candidate skill: {args.name}")
        print(f"   Path: {skill_path}")
        print("\nNext steps:")
        print("   1. Edit the skill file to add validation and failure modes")
        print("   2. Use the skill 3+ times successfully")
        print("   3. Run 'tooeybot skill-promote {name}' to promote it")


if __name__ == "__main__":
    main()
