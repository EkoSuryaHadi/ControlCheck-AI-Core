from controlcheck.persistence.action_repository import evaluate_closure_readiness


def test_closure_blocked_without_evidence():
    result = evaluate_closure_readiness([], evidence_count=0)
    assert result["can_close"] is False
    assert result["evidence_ready"] is False
    assert result["actions_ready"] is True
    assert "At least one evidence record is required before closure." in result["blockers"]


def test_closure_blocked_with_open_action():
    result = evaluate_closure_readiness(["completed", "open"], evidence_count=2)
    assert result["can_close"] is False
    assert result["evidence_ready"] is True
    assert result["actions_ready"] is False
    assert result["open_action_count"] == 1


def test_closure_allowed_when_actions_completed_or_cancelled_and_evidence_exists():
    result = evaluate_closure_readiness(["completed", "cancelled"], evidence_count=3)
    assert result["can_close"] is True
    assert result["evidence_ready"] is True
    assert result["actions_ready"] is True
    assert result["completed_action_count"] == 1
    assert result["blockers"] == []
