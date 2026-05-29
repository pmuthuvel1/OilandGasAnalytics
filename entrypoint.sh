#!/bin/bash

# Oil & Gas Analytics Multi-Agent System Entry Point
# Starts both API (8000) and UI (8001) services

echo "Starting Oil & Gas Analytics System..."

# Validate required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY environment variable is not set!"
    echo "Please set OPENAI_API_KEY before running the application."
    echo ""
    echo "Example:"
    echo "  export OPENAI_API_KEY='your-api-key'"
    echo "  sh entrypoint.sh"
    echo ""
    echo "Or with Docker:"
    echo "  docker run -e OPENAI_API_KEY='your-key' -p 8000:8000 -p 8001:8001 oil-gas-analytics"
    exit 1
fi

echo "✓ OPENAI_API_KEY is set"
echo "✓ OPENAI_MODEL: ${OPENAI_MODEL:-gpt-4}"
echo "✓ OPENAI_BASE_URL: ${OPENAI_BASE_URL:-https://api.openai.com/v1 (default)}"
echo ""
echo "API will run on http://localhost:${API_PORT:-8000}"
echo "UI will run on http://localhost:${UI_PORT:-8001}"
echo ""

# Start API in background
python run.py &
API_PID=$!

# Wait for API to start
sleep 2

# Start UI
python run_ui.py

# If UI exits, kill API
kill $API_PID 2>/dev/null
