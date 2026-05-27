#!/bin/bash

# Oil & Gas Analytics Multi-Agent System Entry Point
# Starts both API (8000) and UI (8001) services

echo "Starting Oil & Gas Analytics System..."
echo "API will run on http://localhost:8000"
echo "UI will run on http://localhost:8001"

# Start API in background
python run.py &
API_PID=$!

# Wait for API to start
sleep 2

# Start UI
python run_ui.py

# If UI exits, kill API
kill $API_PID 2>/dev/null
