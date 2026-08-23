import pytest
from pydantic import ValidationError

from controlcheck.api_models import FindingStatusUpdate


def test_legacy_status_update_rejects_resolved():
    with pytest.raises(ValidationError):
        FindingStatusUpdate(status="resolved")


def test_legacy_status_update_allows_nonclosure_states():
    for status in ("open", "in_review", "dismissed"):
        assert FindingStatusUpdate(status=status).status == status
