# Multi-stage production Dockerfile for ControlCheck AI (Single-Container Fullstack)

# Stage 1: Build Frontend React SPA
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Python builder
FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip build \
    && pip install --no-cache-dir ".[production]"

# Final runtime stage
FROM python:3.11-slim AS runner
WORKDIR /app

# Create non-root system user
RUN groupadd -g 10001 controlcheck && \
    useradd -u 10001 -g controlcheck -s /bin/bash -m controlcheck

# Copy installed python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy built frontend SPA assets from frontend-builder
COPY --from=frontend-builder --chown=controlcheck:controlcheck /app/frontend/dist /app/frontend/dist

# Copy project backend and docker files
COPY --chown=controlcheck:controlcheck pyproject.toml alembic.ini ./
COPY --chown=controlcheck:controlcheck src/ src/
COPY --chown=controlcheck:controlcheck alembic/ alembic/
COPY --chown=controlcheck:controlcheck data/ data/
COPY --chown=controlcheck:controlcheck docker/ docker/

# Install application package
RUN pip install --no-cache-dir -e . && \
    chmod +x /app/docker/entrypoint.sh

# Create var directory for local uploads fallback
RUN mkdir -p var/uploads var/backups && chown -R controlcheck:controlcheck var/

USER 10001:10001

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WEB_CONCURRENCY=2 \
    CONTROLCHECK_CATALOGUE="data/controlcheck_rule_catalogue_v0.2.json"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "controlcheck.asgi:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
