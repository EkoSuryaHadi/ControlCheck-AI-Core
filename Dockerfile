# Multi-stage production Dockerfile for ControlCheck AI
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip build \
    && pip install --no-cache-dir ".[dev]"

# Final runtime stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Create non-root system user
RUN groupadd -g 10001 controlcheck && \
    useradd -u 10001 -g controlcheck -s /bin/bash -m controlcheck

# Copy installed python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project files
COPY --chown=controlcheck:controlcheck pyproject.toml alembic.ini ./
COPY --chown=controlcheck:controlcheck src/ src/
COPY --chown=controlcheck:controlcheck alembic/ alembic/
COPY --chown=controlcheck:controlcheck data/ data/

# Install application package
RUN pip install --no-cache-dir -e .

# Create var directory for local uploads fallback
RUN mkdir -p var/uploads && chown -R controlcheck:controlcheck var/

USER 10001:10001

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONTROLCHECK_CATALOGUE="data/controlcheck_rule_catalogue_v0.2.json"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')" || exit 1

CMD ["uvicorn", "controlcheck.api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
