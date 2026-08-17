from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .builders import normalize_entity
from .ground_truth import GroundTruth
from .models import AuditResult, Finding


Decision = Literal[
    "unreviewed",
    "confirmed_true_positive",
    "valid_finding",
    "dataset_defect",
    "catalogue_ambiguity",
    "threshold_noise",
    "ground_truth_defect",
]


class AdjudicationRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    normalized_entity: str
    actual_present: bool
    expected_present: bool
    actual_severity: str = ""
    expected_severity: str = ""
    decision: Decision = "unreviewed"
    rationale: str = ""
    catalogue_action: str = ""
    dataset_action: str = ""
    ground_truth_action: str = ""
    test_action: str = ""
    prd_action: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return self.rule_id.upper(), self.normalized_entity.upper()


def _actual_entity(finding: Finding) -> str:
    if finding.rule_id.upper() == "CST-004":
        wbs_code = str(finding.metrics.get("wbs_code", "")).strip()
        if not wbs_code:
            raise ValueError(f"CST-004 finding {finding.finding_id} lacks wbs_code evidence")
        return f"{wbs_code}|{normalize_entity(finding.entity_id)}"
    return normalize_entity(finding.entity_id)


def build_adjudication_inventory(
    audit: AuditResult,
    expected: GroundTruth,
) -> list[AdjudicationRow]:
    actual_by_key: dict[tuple[str, str], Finding] = {}
    vendor_keys: dict[str, tuple[str, str]] = {}
    for finding in audit.findings:
        rule_id = finding.rule_id.upper()
        entity = _actual_entity(finding)
        key = rule_id, entity
        if key in actual_by_key:
            raise ValueError(f"Duplicate actual finding key: {key}")
        actual_by_key[key] = finding
        if rule_id == "CST-004":
            vendor_keys[normalize_entity(finding.entity_id)] = key

    expected_by_key = {}
    for item in expected.expected_findings:
        rule_id = item.rule_id.upper()
        raw_entity = getattr(item, "entity_id", None) or getattr(item, "entity")
        entity = normalize_entity(raw_entity)
        key = vendor_keys.get(entity, (rule_id, entity)) if rule_id == "CST-004" else (rule_id, entity)
        if key in expected_by_key:
            raise ValueError(f"Duplicate expected finding key: {key}")
        expected_by_key[key] = item

    rows = []
    for rule_id, entity in sorted(set(actual_by_key) | set(expected_by_key)):
        actual = actual_by_key.get((rule_id, entity))
        expected_item = expected_by_key.get((rule_id, entity))
        rows.append(AdjudicationRow(
            rule_id=rule_id,
            normalized_entity=entity,
            actual_present=actual is not None,
            expected_present=expected_item is not None,
            actual_severity=actual.severity.lower() if actual else "",
            expected_severity=expected_item.severity.lower() if expected_item else "",
        ))
    return rows


def _boolean(value: str, field: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"Invalid {field} boolean at CSV row {row_number}: {value!r}")
    return normalized == "true"


def load_adjudication(path: Path | str) -> list[AdjudicationRow]:
    rows: list[AdjudicationRow] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row_number, raw in enumerate(csv.DictReader(handle), start=2):
            payload = dict(raw)
            payload["actual_present"] = _boolean(payload["actual_present"], "actual_present", row_number)
            payload["expected_present"] = _boolean(payload["expected_present"], "expected_present", row_number)
            rows.append(AdjudicationRow.model_validate(payload))
    keys = [row.key for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Adjudication CSV contains duplicate rule/entity keys")
    return rows

