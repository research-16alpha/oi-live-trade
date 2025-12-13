#!/bin/bash

# Manual start script for Option Chain Monitor
# Use this to start monitoring manually outside of scheduled times

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Starting Option Chain Monitor manually..."
echo ""

# Check if already running
if pgrep -f "automate_oi_monitor.py" > /dev/null; then
    echo "⚠️  Monitor is already running!"
    echo "Process ID: $(pgrep -f 'automate_oi_monitor.py')"
    exit 1
fi

# Start the monitor
./run_monitor.sh

