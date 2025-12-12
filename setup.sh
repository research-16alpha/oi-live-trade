#!/bin/bash

# Setup script for Option Chain Monitor
# This creates a virtual environment and installs dependencies

echo "Setting up Option Chain Monitor..."
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✓ Setup complete!"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "Then you can run:"
echo "  python test_run.py"
echo "  python automate_oi_monitor.py"

