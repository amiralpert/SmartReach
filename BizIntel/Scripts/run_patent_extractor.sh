#!/bin/bash
# Run patent extraction with Python 3.12 that has patent-client

# Change to script directory
cd "$(dirname "$0")"

# Use Python 3.12 where patent-client is installed
echo "Checking Python 3.12 environment..."
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 --version

# Check patent-client
echo "Verifying patent-client installation..."
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -c "import patent_client; print(f'patent-client version: {patent_client.__version__}')" 2>/dev/null || {
    echo "Installing patent-client..."
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pip install patent-client --quiet
}

# Install other dependencies if needed
echo "Installing dependencies..."
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pip install --quiet psycopg2-binary python-dotenv beautifulsoup4 requests hishel 2>/dev/null

# Run the patent extraction
echo ""
echo "Starting patent extraction with patent-client..."
echo "=============================================="
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 Modules/ParallelDataExtraction/Patents/run_patent_extraction.py