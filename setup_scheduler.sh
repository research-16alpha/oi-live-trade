#!/bin/bash

# Setup script for auto-starting Option Chain Monitor
# This installs the Launch Agent to start monitoring at 9:15 AM IST on weekdays

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_NAME="com.oi.monitor.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "=========================================="
echo "Option Chain Monitor - Scheduler Setup"
echo "=========================================="
echo ""

# Check if plist file exists
if [ ! -f "$PLIST_SOURCE" ]; then
    echo "❌ Error: $PLIST_SOURCE not found!"
    exit 1
fi

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Check if already installed
if [ -f "$PLIST_DEST" ]; then
    echo "⚠️  Launch Agent already installed at: $PLIST_DEST"
    read -p "Do you want to reinstall? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    echo "Unloading existing agent..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist file
echo "📋 Copying Launch Agent plist..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Load the Launch Agent
echo "🚀 Loading Launch Agent..."
launchctl load "$PLIST_DEST"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Success! Launch Agent installed and loaded."
    echo ""
    echo "Schedule:"
    echo "  - Starts: 9:15 AM (Monday-Friday)"
    echo "  - Stops: 3:30 PM IST (automatic, handled by script)"
    echo ""
    echo "The monitor will automatically start at 9:15 AM on weekdays."
    echo "It will stop automatically at 3:30 PM IST (after 3:29 PM trading ends)."
    echo ""
    echo "Useful commands:"
    echo "  Check status: launchctl list | grep oi.monitor"
    echo "  Manual start:  ./start_monitor.sh"
    echo "  Manual stop:   ./stop_monitor.sh"
    echo "  Uninstall:     ./uninstall_scheduler.sh"
    echo ""
else
    echo "❌ Error: Failed to load Launch Agent"
    exit 1
fi

