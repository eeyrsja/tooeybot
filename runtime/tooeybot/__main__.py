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


if __name__ == "__main__":
    main()
