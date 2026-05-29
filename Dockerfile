FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data/uploads

# Expose ports
EXPOSE 8000 8001

# Set default environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV API_PORT=8000
ENV UI_PORT=8001
ENV HOST=0.0.0.0

# IMPORTANT: Pass the following environment variables at runtime:
# docker run -e OPENAI_API_KEY="your-key" \
#            -e OPENAI_BASE_URL="https://api.core42.ai/v1" \
#            -e OPENAI_MODEL="gpt-4" \
#            -p 8000:8000 -p 8001:8001 oil-gas-analytics
#
# Or use --env-file:
# docker run --env-file .env -p 8000:8000 -p 8001:8001 oil-gas-analytics

# Default entry point - runs both API and UI
CMD ["sh", "entrypoint.sh"]
