from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from tests.persistence.test_snapshot_analysis_service import snapshot_harness  # noqa: F401

from controlcheck.models import EvidenceItem, Finding
from controlcheck.persistence.models import FindingEvidenceRecord, FindingRecord
from controlcheck.service import run_audit


def _persisted_findings(session_factory, run_id):
    with session_factory() as session:
        records = list(session.scalars(
            select(FindingRecord).where(FindingRecord.analysis_run_id == run_id)
        ))
        result = []
        for record in records:
            evidence = list(session.scalars(
                select(FindingEvidenceRecord)
                .where(FindingEvidenceRecord.finding_id == record.id)
                .order_by(FindingEvidenceRecord.evidence_order)
            ))
            result.append(Finding(
                finding_id=record.engine_finding_id,
                rule_id=record.rule_id,
                rule_name=record.rule_name,
                category=record.category,
                severity=record.severity,
                project_id=str(record.project_id),
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                title=record.title,
                description=record.description,
                metrics=record.metrics,
                business_impact=record.business_impact,
                recommendation=record.recommendation,
                confidence=float(record.confidence),
                evidence=[EvidenceItem(
                    source_sheet=item.source_sheet,
                    source_rows=item.source_rows,
                    record_ids=item.record_ids,
                    fields=item.fields,
                    aggregation=item.aggregation,
                ) for item in evidence],
                calculation=record.calculation,
            ))
        return sorted(result, key=lambda item: (item.rule_id, item.entity_id))


def test_golden_excel_and_database_snapshot_findings_are_identical(snapshot_harness, project_root: Path):
    session_factory, _, service, organization_id, project_id, snapshot = snapshot_harness
    expected = sorted(
        run_audit(
            project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
            project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        ).findings,
        key=lambda item: (item.rule_id, item.entity_id),
    )
    run = service.run_snapshot(organization_id, project_id, snapshot.id)
    actual = _persisted_findings(session_factory, run.id)
    assert run.finding_count == len(expected) == 59
    actual_dump = [item.model_dump(mode="json") for item in actual]
    expected_dump = [item.model_dump(mode="json") for item in expected]
    # project_id is the tenant database UUID in the durable record; all engine
    # identity, metrics, calculations, and source evidence must remain equal.
    for actual_item, expected_item in zip(actual_dump, expected_dump, strict=True):
        actual_item["project_id"] = expected_item["project_id"]
    assert actual_dump == expected_dump
    with session_factory() as session:
        evidence = list(session.scalars(
            select(FindingEvidenceRecord)
            .join(FindingRecord, FindingRecord.id == FindingEvidenceRecord.finding_id)
            .where(FindingRecord.analysis_run_id == run.id)
        ))
    assert evidence and all(item.raw_row_ids for item in evidence)
