import pytest

import controlcheck.application as application


def test_health_availability_marks_all_blocked_as_not_computed() -> None:
    classify = getattr(application, "classify_health_availability", None)
    assert classify is not None, "health availability classification is required"

    status, coverage, domains = classify(
        [],
        [
            {
                "rule_id": "CST-001",
                "reason_code": "blocked_required_domain",
                "blocked_domains": ["budget", "actual_cost"],
            },
            {
                "rule_id": "SCH-001",
                "reason_code": "blocked_required_domain",
                "blocked_domains": ["schedule"],
            },
        ],
    )

    assert status == "not_computed"
    assert coverage == 0
    assert domains == ["actual_cost", "budget", "schedule"]


def test_health_availability_marks_skipped_rules_as_partial() -> None:
    classify = getattr(application, "classify_health_availability", None)
    assert classify is not None, "health availability classification is required"

    status, coverage, domains = classify(
        ["CST-001", "CST-002", "CST-003"],
        [
            {
                "rule_id": "PRG-001",
                "reason_code": "blocked_required_domain",
                "blocked_domains": ["progress"],
            },
            {
                "rule_id": "PRG-002",
                "reason_code": "blocked_required_domain",
                "blocked_domains": ["progress"],
            },
        ],
    )

    assert status == "partial"
    assert coverage == pytest.approx(3 / 5)
    assert domains == ["progress"]
