# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Oil & Gas Analytics Multi-Agent System
# Production-grade container build.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# System deps (kept minimal)
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc curl tini \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Runtime dirs + non-root user
RUN mkdir -p logs data/uploads \
 && groupadd --system app \
 && useradd  --system --gid app --home ${APP_HOME} app \
 && chown -R app:app ${APP_HOME}

USER app

EXPOSE 8000 8001

# Defaults; OPENAI_API_KEY / OPENAI_BASE_URL MUST be supplied at runtime
# (unless SAMPLE_MODE=true, which runs the system without any API key).
ENV APP_ENV=production \
    LOG_LEVEL=INFO \
    JSON_LOGS=true \
    API_PORT=8000 \
    UI_PORT=8001 \
    HOST=0.0.0.0 \
    OPENAI_MODEL=gpt-4.1 \
    COMPASS_CHAT_MODEL=gpt-4.1 \
    COMPASS_REASONING_MODEL=gpt-5.1 \
    SAMPLE_MODE=false

# Container healthcheck hits the liveness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${API_PORT}/health" || exit 1

# Pass secrets via -e or --env-file, e.g.:
#   docker run --env-file .env -p 8000:8000 -p 8001:8001 oil-gas-analytics
ENTRYPOINT ["/usr/bin/tini", "--", "sh", "entrypoint.sh"]

