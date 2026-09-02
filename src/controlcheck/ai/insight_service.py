from __future__ import annotations

import os
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from ..logging import get_logger
from ..persistence.repositories import (
    AIInsightRepository,
    AnalysisRepository,
    FindingRepository,
    HealthRepository,
    ProjectRepository,
)
from .insights import OpenAIInsightClient, build_insight_input

logger = get_logger("ai.insight_service")


class AIInsightGenerationService:
    """Generate one bounded, evidence-grounded insight for a completed run."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        client_factory: Callable[[], OpenAIInsightClient] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.client_factory = client_factory or self._configured_client

    def ensure_pending(self, organization_id: UUID, project_id: UUID, run_id: UUID) -> None:
        with self.session_factory() as session:
            run = AnalysisRepository(session).get_run(organization_id, run_id)
            if run is None or run.project_id != project_id:
                return
            AIInsightRepository(session).ensure_pending(organization_id, project_id, run_id)
            session.commit()

    def generate(self, organization_id: UUID, run_id: UUID) -> None:
        with self.session_factory() as session:
            run = AnalysisRepository(session).get_run(organization_id, run_id)
            if run is None or run.status not in {"succeeded", "completed"}:
                return
            repository = AIInsightRepository(session)
            record = repository.ensure_pending(organization_id, run.project_id, run_id)
            if not repository.begin_generation(record):
                session.commit()
                return
            project = ProjectRepository(session).get_scoped(organization_id, run.project_id)
            findings, _ = FindingRepository(session).list_for_run(
                organization_id, run_id, limit=10000
            )
            health = HealthRepository(session).get_by_run(organization_id, run_id)
            facts = build_insight_input(
                project_name=project.name if project else "Project",
                findings=findings,
                unavailable_domains=list(health.unavailable_domains) if health else [],
            )
            allowed_finding_ids = {str(finding.id) for finding in findings}
            session.commit()

        try:
            client = self.client_factory()
            content = client.generate(facts, allowed_finding_ids=allowed_finding_ids)
        except ValueError:
            self._fail(organization_id, run_id, "ai_invalid_response")
            logger.warning("AI Insight provider returned invalid response for run %s", run_id)
            return
        except Exception:
            self._fail(organization_id, run_id, "ai_provider_unavailable")
            logger.exception("AI Insight generation failed for run %s", run_id)
            return

        with self.session_factory() as session:
            record = AIInsightRepository(session).get_for_run(organization_id, run_id)
            if record is not None:
                AIInsightRepository(session).complete(record, content, client.model)
                session.commit()

    def _fail(self, organization_id: UUID, run_id: UUID, error_code: str) -> None:
        with self.session_factory() as session:
            record = AIInsightRepository(session).get_for_run(organization_id, run_id)
            if record is not None:
                AIInsightRepository(session).fail(record, error_code)
                session.commit()

    @staticmethod
    def _configured_client() -> OpenAIInsightClient:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OpenAI API key is not configured")
        return OpenAIInsightClient(
            api_key,
            model=os.environ.get("CONTROLCHECK_OPENAI_MODEL", "gpt-4.1-mini"),
        )