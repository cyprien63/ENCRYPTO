#!/bin/bash
# =========================================
#       ENCRYPTO launcher for Linux        
# =========================================

echo "========================================="
echo "      ENCRYPTO launcher for Linux        "
echo "========================================="
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in your PATH."
    echo "Please install Python 3 and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating virtual environment (.venv)..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
fi

# Activate virtual environment
echo "[INFO] Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment."
    exit 1
fi

# Install/Upgrade dependencies
echo "[INFO] Installing/Checking dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies."
    exit 1
fi

# Run application
echo "[INFO] Launching ENCRYPTO..."
python3 app.py
if [ $? -ne 0 ]; then
    echo "[WARNING] ENCRYPTO exited with an error code."
fi

exit 0
