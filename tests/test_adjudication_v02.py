from pathlib import Path

from controlcheck.adjudication import (
    build_adjudication_inventory,
    load_adjudication,
)
from controlcheck.ground_truth import load_ground_truth
from controlcheck.models import AuditResult


def _v01_artifacts(project_root: Path):
    audit = AuditResult.model_validate_json(
        (project_root / "results" / "findings_v0.1.json").read_text(encoding="utf-8")
    )
    expected = load_ground_truth(
        project_root / "data" / "controlcheck_expected_findings_v0.1.json"
    )
    return audit, expected


def test_adjudication_covers_actual_union_expected(project_root: Path):
    audit, expected = _v01_artifacts(project_root)
    inventory = build_adjudication_inventory(audit, expected)
    decisions = load_adjudication(project_root / "validation" / "adjudication_v0.2.csv")

    assert {row.key for row in decisions} == {row.key for row in inventory}
    assert len(decisions) == len({row.key for row in decisions})
    assert all(row.decision != "unreviewed" and row.rationale.strip() for row in decisions)


def test_adjudication_has_explicit_disposition_for_every_artifact(project_root: Path):
    rows = load_adjudication(project_root / "validation" / "adjudication_v0.2.csv")

    assert all(
        row.catalogue_action
        and row.dataset_action
        and row.ground_truth_action
        and row.test_action
        and row.prd_action
        for row in rows
    )


def test_adjudication_encodes_approved_alignment_decisions(project_root: Path):
    rows = {
        row.key: row
        for row in load_adjudication(
            project_root / "validation" / "adjudication_v0.2.csv"
        )
    }

    assert rows[("CST-001", "3.1")].decision == "dataset_defect"
    assert rows[("CST-002", "3.3")].decision == "dataset_defect"
    assert rows[("PRG-003", "3.1")].decision == "dataset_defect"
    assert rows[("PRG-003", "4.0")].decision == "threshold_noise"
    assert rows[("CST-005", "ACT-9006")].catalogue_action == "tighten_dual_materiality"
    assert all(
        "|" in row.normalized_entity
        for row in rows.values()
        if row.rule_id == "CST-004"
    )

