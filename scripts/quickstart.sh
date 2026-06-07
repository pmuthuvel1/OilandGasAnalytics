#!/bin/bash

# Oil & Gas Analytics - Quick Start Helper Script

echo "=========================================="
echo "Oil & Gas Analytics Multi-Agent System"
echo "=========================================="
echo ""

# Check Python version
python_version=$(python --version 2>&1)
echo "✓ Python: $python_version"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment (Unix-like)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    source venv/bin/activate
elif [[ "$OSTYPE" == "darwin"* ]]; then
    source venv/bin/activate
elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
    source venv/Scripts/activate || . venv/Scripts/activate
fi

echo "✓ Virtual environment activated"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Create necessary directories
mkdir -p logs data/uploads

# Check environment file
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠ .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env created - Please edit and add your OPENAI_API_KEY"
    echo ""
    exit 1
fi

echo ""
echo "=========================================="
echo "Ready to start!"
echo "=========================================="
echo ""
echo "Start services in separate terminals:"
echo ""
echo "Terminal 1 (API - port 8000):"
echo "  python run.py"
echo ""
echo "Terminal 2 (UI - port 8001):"
echo "  python run_ui.py"
echo ""
echo "Or run everything with Docker:"
echo "  docker build -t oil-gas-analytics ."
echo "  docker run -p 8000:8000 -p 8003:8003 --env-file .env oil-gas-analytics"
echo ""
echo "Access the system:"
echo "  - API: http://localhost:8000"
echo "  - Dashboard: http://localhost:8001"
echo "  - Docs: http://localhost:8000/docs"
echo ""
