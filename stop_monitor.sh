#!/bin/bash

# Stop script for Option Chain Monitor
# Use this to stop monitoring manually

echo "Stopping Option Chain Monitor..."

# Find and kill the process
PID=$(pgrep -f "automate_oi_monitor.py")

if [ -z "$PID" ]; then
    echo "⚠️  Monitor is not running."
    exit 0
fi

echo "Found process ID: $PID"
kill "$PID"

# Wait a moment and check if it's still running
sleep 2

if pgrep -f "automate_oi_monitor.py" > /dev/null; then
    echo "⚠️  Process still running, forcing kill..."
    kill -9 "$PID" 2>/dev/null
fi

echo "✅ Monitor stopped."

