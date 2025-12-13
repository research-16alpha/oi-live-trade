#!/bin/bash

# Uninstall script for Launch Agent scheduler

PLIST_NAME="com.oi.monitor.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "=========================================="
echo "Option Chain Monitor - Scheduler Uninstall"
echo "=========================================="
echo ""

# Check if installed
if [ ! -f "$PLIST_DEST" ]; then
    echo "⚠️  Launch Agent not found. Nothing to uninstall."
    exit 0
fi

# Stop any running instances
echo "🛑 Stopping any running monitor instances..."
./stop_monitor.sh 2>/dev/null || true

# Unload the Launch Agent
echo "📋 Unloading Launch Agent..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Remove the plist file
echo "🗑️  Removing Launch Agent plist..."
rm -f "$PLIST_DEST"

echo ""
echo "✅ Launch Agent uninstalled successfully."
echo "The monitor will no longer auto-start on weekdays."
echo ""
echo "You can still start it manually with: ./start_monitor.sh"

