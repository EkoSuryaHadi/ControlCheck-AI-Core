FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

RUN groupadd --gid 10001 controlcheck \
    && useradd --uid 10001 --gid 10001 --create-home \
        --home-dir /home/controlcheck --shell /usr/sbin/nologin controlcheck \
    && mkdir -p /var/lib/controlcheck/uploads \
    && chown -R controlcheck:controlcheck /var/lib/controlcheck /app

COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

COPY alembic.ini ./
COPY alembic ./alembic
COPY data ./data
COPY docker/entrypoint.sh /usr/local/bin/controlcheck-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/controlcheck-entrypoint \
    && chmod 0555 /usr/local/bin/controlcheck-entrypoint \
    && chown -R controlcheck:controlcheck /app

USER controlcheck

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; host=os.environ['CONTROLCHECK_TRUSTED_HOSTS'].split(',')[0].strip(); request=urllib.request.Request('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health/live',headers={'Host':host}); urllib.request.urlopen(request,timeout=3)"

ENTRYPOINT ["/usr/local/bin/controlcheck-entrypoint"]
