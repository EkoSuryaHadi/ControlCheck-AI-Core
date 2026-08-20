from unittest.mock import MagicMock, patch
from uuid import uuid4

from controlcheck.ai.assistant import ProjectAIAssistant
from controlcheck.ai.safety import AI_SAFETY_RULES, sanitize_ai_response
from controlcheck.persistence.models import AIConversationRecord, AIMessageRecord
from controlcheck.persistence.repositories import AIRepository


def test_ai_safety_rules_and_sanitizer():
    assert len(AI_SAFETY_RULES) >= 5
    raw_response = {"answer": "Health is 90.0"}
    sanitized = sanitize_ai_response(raw_response)
    assert sanitized["answer"] == "Health is 90.0"
    assert sanitized["key_evidence"] == []
    assert sanitized["confidence"] == "high"
    assert sanitized["data_caveat"] is None


def test_ai_assistant_health_intent():
    mock_session = MagicMock()
    org_id = uuid4()
    proj_id = uuid4()

    assistant = ProjectAIAssistant(org_id, proj_id, mock_session)

    with patch("controlcheck.ai.assistant.get_project_health") as mock_health:
        mock_health.return_value = {
            "overall_score": 85.5,
            "score_band": "Healthy",
            "cost_score": 90.0,
            "schedule_score": 80.0,
            "progress_score": 90.0,
            "dq_score": 80.0,
            "key_drivers": [],
        }

        result = assistant.ask("What is the current health of this project?")
        assert "85.5/100" in result["answer"]
        assert "Healthy" in result["answer"]
        assert result["confidence"] == "high"


def test_ai_assistant_cost_intent():
    mock_session = MagicMock()
    org_id = uuid4()
    proj_id = uuid4()

    assistant = ProjectAIAssistant(org_id, proj_id, mock_session)

    with patch("controlcheck.ai.assistant.get_top_cost_drivers") as mock_cost:
        mock_cost.return_value = [
            {
                "finding_id": "FIND-COST-1",
                "rule_id": "CST-001",
                "entity_id": "WBS-100",
                "title": "Actual cost exceeds budget",
                "description": "Spent $1.2M vs $1.0M budget",
                "business_impact": "Cost overrun",
                "recommendation": "Investigate invoice TX-10",
            }
        ]

        result = assistant.ask("Are there any cost overruns or budget issues?")
        assert "FIND-COST-1" in result["answer"]
        assert "WBS-100" in result["answer"]
        assert "FIND-COST-1" in result["evidence_references"]


def test_ai_assistant_schedule_intent():
    mock_session = MagicMock()
    org_id = uuid4()
    proj_id = uuid4()

    assistant = ProjectAIAssistant(org_id, proj_id, mock_session)

    with patch("controlcheck.ai.assistant.get_delayed_activities") as mock_sched:
        mock_sched.return_value = [
            {
                "finding_id": "FIND-SCH-1",
                "rule_id": "SCH-001",
                "activity_id": "ACT-500",
                "title": "Overdue Foundation Activity",
                "description": "Foundation is 14 days late",
                "business_impact": "Milestone slip",
                "recommendation": "Fast-track steel supply",
            }
        ]

        result = assistant.ask("Why is the schedule delayed?")
        assert "ACT-500" in result["answer"]
        assert "Foundation" in result["answer"]
        assert "FIND-SCH-1" in result["evidence_references"]


def test_ai_repository_crud():
    mock_session = MagicMock()
    org_id = uuid4()
    proj_id = uuid4()
    user_id = uuid4()

    repo = AIRepository(mock_session)

    conv = repo.create_conversation(
        organization_id=org_id,
        project_id=proj_id,
        user_id=user_id,
        title="Audit Q&A",
    )
    assert conv.title == "Audit Q&A"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()

    msg = repo.add_message(
        conversation_id=conv.id,
        role="user",
        content="What is the health?",
    )
    assert msg.role == "user"
    assert msg.content == "What is the health?"
