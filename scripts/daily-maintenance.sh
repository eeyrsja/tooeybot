#!/bin/bash
# Tooeybot Daily Maintenance Script
# Add to crontab: 0 0 * * * /path/to/daily-maintenance.sh

set -e

# Configuration
TOOEYBOT_DIR="${TOOEYBOT_DIR:-$HOME/dev/tooeybot}"
RUNTIME_DIR="$TOOEYBOT_DIR/runtime"
LOG_FILE="$TOOEYBOT_DIR/agent/logs/maintenance.log"

# Activate virtual environment
source "$RUNTIME_DIR/venv/bin/activate"

# Change to runtime directory
cd "$RUNTIME_DIR"

# Run maintenance with logging
echo "=== Daily Maintenance: $(date -Iseconds) ===" >> "$LOG_FILE"
python -m tooeybot maintain >> "$LOG_FILE" 2>&1

echo "Maintenance complete: $(date -Iseconds)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
