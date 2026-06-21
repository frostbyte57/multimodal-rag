FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for compiling psycopg and other packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration and code
COPY pyproject.toml .
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY eval/ ./eval/

# Install the application and all optional dependencies
RUN pip install --no-cache-dir -e .[tui,cloud,pdf]

# Ensure data directory exists
RUN mkdir -p data/corpus

# TUI is the default application to run
CMD ["mmrag-tui"]
