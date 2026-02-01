"""
Tooeybot CLI entry point.
"""

import argparse
import sys
from pathlib import Path

from .config import load_config
from .agent import Agent
from .logger import setup_logging


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


if __name__ == "__main__":
    main()
