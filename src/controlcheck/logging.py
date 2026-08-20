from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Context variables for tracing across async/sync boundaries
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
organization_id_ctx: ContextVar[str | None] = ContextVar("organization_id", default=None)
project_id_ctx: ContextVar[str | None] = ContextVar("project_id", default=None)
analysis_run_id_ctx: ContextVar[str | None] = ContextVar("analysis_run_id", default=None)


def set_log_context(
    *,
    request_id: str | None = None,
    organization_id: str | None = None,
    project_id: str | None = None,
    analysis_run_id: str | None = None,
) -> None:
    if request_id is not None:
        request_id_ctx.set(str(request_id))
    if organization_id is not None:
        organization_id_ctx.set(str(organization_id))
    if project_id is not None:
        project_id_ctx.set(str(project_id))
    if analysis_run_id is not None:
        analysis_run_id_ctx.set(str(analysis_run_id))


def clear_log_context() -> None:
    request_id_ctx.set(None)
    organization_id_ctx.set(None)
    project_id_ctx.set(None)
    analysis_run_id_ctx.set(None)


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Contextual correlation IDs
        req_id = getattr(record, "request_id", None) or request_id_ctx.get()
        if req_id:
            payload["request_id"] = req_id

        org_id = getattr(record, "organization_id", None) or organization_id_ctx.get()
        if org_id:
            payload["organization_id"] = str(org_id)

        proj_id = getattr(record, "project_id", None) or project_id_ctx.get()
        if proj_id:
            payload["project_id"] = str(proj_id)

        run_id = getattr(record, "analysis_run_id", None) or analysis_run_id_ctx.get()
        if run_id:
            payload["analysis_run_id"] = str(run_id)

        # Standard extra attributes passed by caller
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            for k, v in record.extra_data.items():
                if k not in payload:
                    payload[k] = v

        # If exc_info is present, serialize it safely
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exception"] = record.exc_text

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: str | int | None = None,
    log_format: str | None = None,
) -> None:
    """Configures root/package logging according to environment or arguments."""
    target_level = level or os.environ.get("CONTROLCHECK_LOG_LEVEL", "INFO")
    target_format = log_format or os.environ.get("CONTROLCHECK_LOG_FORMAT", "text").lower()

    if isinstance(target_level, str):
        target_level = getattr(logging, target_level.upper(), logging.INFO)

    root_logger = logging.getLogger("controlcheck")
    root_logger.setLevel(target_level)

    # Avoid duplicate handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(target_level)

    if target_format == "json":
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger namespaced under controlcheck."""
    if not name.startswith("controlcheck"):
        name = f"controlcheck.{name}"
    return logging.getLogger(name)
