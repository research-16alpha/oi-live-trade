#!/bin/bash

# Activate virtual environment and run test
# Loads credentials if credentials.sh exists
if [ -f credentials.sh ]; then
    source credentials.sh
fi
source venv/bin/activate
python test_run.py

