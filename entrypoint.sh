#!/usr/bin/env bash
# Oil & Gas Analytics Multi-Agent System Entry Point
# Starts both API (8000) and UI (8003, legacy run_ui_old.py) services with
# proper signal handling.

set -euo pipefail

APP_ENV="${APP_ENV:-production}"
API_PORT="${API_PORT:-8000}"
# Default UI port is 8003 since run_ui.py was renamed to run_ui_old.py.
# Set UI_OLD_PORT directly if you want to override per-process; UI_PORT is
# kept as a back-compat alias.
UI_PORT="${UI_PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
LOG_LEVEL="${LOG_LEVEL:-info}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
SAMPLE_MODE="${SAMPLE_MODE:-false}"

echo "Starting Oil & Gas Analytics System (APP_ENV=${APP_ENV})..."

# In production we REQUIRE an API key, unless explicitly running in sample mode.
if [ "${APP_ENV}" = "production" ] && [ "${SAMPLE_MODE,,}" != "true" ]; then
    if [ -z "${OPENAI_API_KEY:-}" ]; then
        echo "ERROR: OPENAI_API_KEY environment variable is not set!" >&2
        echo "Set it via -e OPENAI_API_KEY=... or --env-file, or run with SAMPLE_MODE=true." >&2
        exit 1
    fi
fi

if [ -n "${OPENAI_API_KEY:-}" ]; then
    KEY_STATUS="set"
else
    KEY_STATUS="<not set>"
fi

echo "✓ APP_ENV:          ${APP_ENV}"
echo "✓ SAMPLE_MODE:      ${SAMPLE_MODE}"
echo "✓ OPENAI_API_KEY:   ${KEY_STATUS}"
echo "✓ OPENAI_MODEL:     ${OPENAI_MODEL:-gpt-4.1}"
echo "✓ OPENAI_BASE_URL:  ${OPENAI_BASE_URL:-https://api.core42.ai/v1 (default fallback)}"
echo "✓ COMPASS_CHAT:     ${COMPASS_CHAT_MODEL:-gpt-4.1}"
echo "✓ COMPASS_REASONING:${COMPASS_REASONING_MODEL:-gpt-5.1}"
echo "✓ API:              http://${HOST}:${API_PORT}"
echo "✓ UI:               http://${HOST}:${UI_PORT}"
echo ""

API_PID=""
UI_PID=""

term_handler() {
    echo "Received shutdown signal; stopping..."
    if [ -n "${API_PID}" ] && kill -0 "${API_PID}" 2>/dev/null; then
        kill -TERM "${API_PID}" 2>/dev/null || true
    fi
    if [ -n "${UI_PID}" ] && kill -0 "${UI_PID}" 2>/dev/null; then
        kill -TERM "${UI_PID}" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    exit 0
}
trap term_handler SIGTERM SIGINT

# Start API with gunicorn + uvicorn workers in production, plain uvicorn in dev
if [ "${APP_ENV}" = "production" ]; then
    gunicorn run:app \
        --workers "${WEB_CONCURRENCY}" \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind "${HOST}:${API_PORT}" \
        --timeout "${GUNICORN_TIMEOUT}" \
        --graceful-timeout 30 \
        --access-logfile - \
        --error-logfile - \
        --log-level "${LOG_LEVEL}" \
        --forwarded-allow-ips "*" &
else
    python run.py &
fi
API_PID=$!

# Start UI (legacy dashboard; module was renamed from run_ui.py → run_ui_old.py)
UI_OLD_PORT="${UI_PORT}" python run_ui_old.py &
UI_PID=$!

# Wait for either process to exit; propagate exit status
set +e
wait -n "${API_PID}" "${UI_PID}"
EXIT_CODE=$?
set -e
term_handler
exit "${EXIT_CODE}"

