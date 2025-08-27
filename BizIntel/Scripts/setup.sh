#!/bin/bash

# SmartReach BizIntel Setup Script
# This script sets up the Python environment and installs dependencies

echo "======================================"
echo "SmartReach BizIntel Setup"
echo "======================================"

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install production requirements
echo ""
echo "Installing production dependencies..."
pip install -r requirements.txt

# Ask about development dependencies
echo ""
read -p "Install development dependencies? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing development dependencies..."
    pip install -r requirements-dev.txt
fi

# Install Playwright browsers (needed for web scraping)
echo ""
echo "Installing Playwright browsers..."
playwright install chromium

# Check PostgreSQL connection
echo ""
echo "Testing database connection..."
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        database='smartreachbizintel',
        user='srbiuser',
        password='SRBI_dev_2025'
    )
    print('✅ Database connection successful!')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"

# Check .env file
echo ""
if [ -f "config/.env" ]; then
    echo "✅ Config file found: config/.env"
else
    echo "⚠️  Config file not found. Please create config/.env with your settings"
fi

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "To activate the environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run the extraction pipeline:"
echo "  python Modules/ParallelDataExtraction/Orchestration/run_orchestration.py"
echo ""