from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from controlcheck.models import AuditResult, EvidenceItem, Finding
from controlcheck.persistence.models import FindingEvidenceRecord, FindingRecord
from controlcheck.persistence.repositories import AnalysisRepository


class RecordingSession:
    def __init__(self, run):
        self.run = run
        self.added = []
        self.flush_count = 0

    def get(self, _model, _run_id):
        return self.run

    def add(self, record):
        self.added.append(record)

    def add_all(self, records):
        self.added.extend(records)

    def flush(self):
        self.flush_count += 1
        for record in self.added:
            if isinstance(record, FindingRecord) and record.id is None:
                record.id = uuid4()


def _finding(index: int) -> Finding:
    return Finding(
        finding_id=f"SCH-001:{index}",
        rule_id="SCH-001",
        rule_name="Overdue Activity",
        category="schedule",
        severity="warning",
        project_id="ABACUS-1",
        entity_type="activity",
        entity_id=str(index),
        title="Activity overdue",
        description="Schedule activity has passed its baseline finish.",
        metrics={"days_overdue": 1},
        business_impact="Schedule risk",
        recommendation="Review the activity.",
        evidence=[
            EvidenceItem(
                source_sheet="Schedule",
                source_rows=[index + 3],
                record_ids=[str(index)],
                fields={"activity_id": str(index)},
            )
        ],
        calculation={"days_overdue": 1},
    )


def test_complete_run_batches_finding_and_evidence_persistence():
    run = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        status="running",
        rule_count=0,
        finding_count=0,
        executed_rule_ids=[],
        skipped_rules=[],
        duration_ms=0,
        completed_at=None,
    )
    session = RecordingSession(run)
    audit = AuditResult(
        project_id="ABACUS-1",
        data_date=date(2026, 9, 2),
        rule_count=1,
        finding_count=4,
        findings=[_finding(index) for index in range(4)],
    )

    AnalysisRepository(session).complete_run(
        run.id,
        audit,
        duration_ms=10,
        raw_row_index={("Schedule", index + 3): index + 100 for index in range(4)},
    )

    findings = [record for record in session.added if isinstance(record, FindingRecord)]
    evidence = [record for record in session.added if isinstance(record, FindingEvidenceRecord)]
    assert len(findings) == 4
    assert len(evidence) == 4
    assert all(record.finding_id for record in evidence)
    assert session.flush_count <= 3