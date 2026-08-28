import pytest

from controlcheck.telemetry import ALLOWED_EVENTS, sanitize_event_metadata, validate_event_name


def test_allowlisted_event_name_is_accepted():
    assert validate_event_name("analysis_completed") == "analysis_completed"


def test_unknown_event_name_is_rejected():
    with pytest.raises(ValueError):
        validate_event_name("secret_internal_event")


def test_sensitive_workbook_metadata_is_rejected():
    with pytest.raises(ValueError):
        sanitize_event_metadata({"workbook_cells": "A1:B9"})


def test_safe_metadata_is_normalized_and_bounded():
    result = sanitize_event_metadata({"source": "beta", "finding_count": 12})
    assert result == {"source": "beta", "finding_count": 12}
    assert ALLOWED_EVENTS
