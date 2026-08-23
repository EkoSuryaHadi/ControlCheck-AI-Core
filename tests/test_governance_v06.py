from datetime import datetime, timezone

from controlcheck.governance import GovernancePolicy, approval_gate, can_decide_approval, finding_due_at, finding_is_overdue


def test_critical_finding_uses_three_day_default_sla():
    detected = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)
    policy = GovernancePolicy()
    assert finding_due_at(detected, "critical", policy) == datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)
    assert finding_is_overdue(detected, "critical", policy, datetime(2026, 8, 23, 8, 1, tzinfo=timezone.utc)) is True


def test_critical_closure_requires_approved_decision_by_default():
    gate = approval_gate(severity="critical", policy=GovernancePolicy(), latest_decision=None)
    assert gate["approval_required"] is True
    assert gate["approval_ready"] is False
    approved = approval_gate(severity="critical", policy=GovernancePolicy(), latest_decision="approved")
    assert approved["approval_ready"] is True


def test_warning_does_not_require_approval_by_default():
    gate = approval_gate(severity="warning", policy=GovernancePolicy(), latest_decision=None)
    assert gate["approval_required"] is False
    assert gate["approval_ready"] is True


def test_maker_checker_blocks_self_approval():
    allowed, reason = can_decide_approval(
        requester_user_id="user-1",
        approver_user_id="user-1",
        approver_role="org_admin",
    )
    assert allowed is False
    assert "Maker-checker" in reason


def test_only_managerial_authority_may_approve():
    allowed, _ = can_decide_approval(
        requester_user_id="user-1",
        approver_user_id="user-2",
        approver_role="project_member",
    )
    assert allowed is False
    allowed, reason = can_decide_approval(
        requester_user_id="user-1",
        approver_user_id="user-2",
        approver_role="project_manager",
    )
    assert allowed is True
    assert reason is None
