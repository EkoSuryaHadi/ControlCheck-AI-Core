from __future__ import annotations

import json
import re

ALLOWED_EVENTS: frozenset[str] = frozenset({
    "registration_completed", "project_created", "upload_accepted", "upload_failed",
    "analysis_completed", "analysis_failed", "finding_viewed", "evidence_viewed",
    "finding_exported", "finding_status_changed", "run_feedback_submitted",
    "finding_feedback_submitted", "demo_login_used", "login_started", "login_completed",
    "login_failed", "registration_started", "registration_failed", "analysis_progress_viewed",
    "actions_workspace_viewed", "finding_detail_viewed", "finding_closure_blocked",
    "finding_closed", "finding_action_created", "finding_action_status_changed",
})

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SENSITIVE = ("workbook", "cell", "raw", "vendor", "password", "token", "secret", "content", "path", "file")


def validate_event_name(event_name: str) -> str:
    if not isinstance(event_name, str) or event_name not in ALLOWED_EVENTS:
        raise ValueError("event_name is not allowlisted")
    return event_name


def sanitize_event_metadata(metadata: dict | None) -> dict:
    if metadata is None:
        return {}
    if not isinstance(metadata, dict) or len(metadata) > 20:
        raise ValueError("metadata must be an object with at most 20 keys")
    clean: dict[str, str | int | float | bool | None] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key) or any(part in key.lower() for part in _SENSITIVE):
            raise ValueError("metadata contains a restricted key")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError("metadata values must be scalar")
        if isinstance(value, str) and len(value) > 200:
            raise ValueError("metadata string value is too long")
        clean[key] = value
    if len(json.dumps(clean, separators=(",", ":"))) > 4096:
        raise ValueError("metadata is too large")
    return clean
