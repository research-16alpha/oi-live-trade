#!/bin/bash

# Activate virtual environment and run monitor
# Loads credentials if credentials.sh exists
if [ -f credentials.sh ]; then
    source credentials.sh
fi
source venv/bin/activate
python automate_oi_monitor.py

