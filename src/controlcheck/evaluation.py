from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .builders import normalize_entity
from .models import Finding


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedFinding(EvalModel):
    expected_id: str
    rule_id: str
    category: str
    severity: str
    source: str
    entity: str
    finding_title: str
    why_expected: str


class GroundTruth(EvalModel):
    dataset_version: str
    project_id: str
    data_date: date
    expected_finding_count: int
    expected_findings: list[ExpectedFinding]


class EvaluationReport(EvalModel):
    executed_rule_count: int = 0
    deterministic: bool = False
    expected_count: int
    actual_count: int
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    false_positives: list[dict]
    false_negatives: list[ExpectedFinding]
    severity_matches: int
    severity_mismatches: list[dict]
    per_rule: dict[str, dict[str, int]]


def load_ground_truth(path: Path | str) -> GroundTruth:
    result = GroundTruth.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    if result.expected_finding_count != len(result.expected_findings):
        raise ValueError("Ground-truth count does not match expected_findings length")
    return result


def _key(rule_id: str, entity: str) -> tuple[str, str]:
    return rule_id.upper(), normalize_entity(entity)


def evaluate(findings: list[Finding], expected: GroundTruth) -> EvaluationReport:
    actual_by_key = {_key(item.rule_id, item.entity_id): item for item in findings}
    expected_by_key = {_key(item.rule_id, item.entity): item for item in expected.expected_findings}
    matched_keys = set(actual_by_key) & set(expected_by_key)
    fp_keys = sorted(set(actual_by_key) - set(expected_by_key))
    fn_keys = sorted(set(expected_by_key) - set(actual_by_key))
    tp, fp, fn = len(matched_keys), len(fp_keys), len(fn_keys)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    severity_mismatches = []
    severity_matches = 0
    for key in sorted(matched_keys):
        actual_severity = actual_by_key[key].severity.lower()
        expected_severity = expected_by_key[key].severity.lower()
        if actual_severity == expected_severity:
            severity_matches += 1
        else:
            severity_mismatches.append({
                "rule_id": key[0], "entity": key[1],
                "expected": expected_severity, "actual": actual_severity,
            })
    rule_ids = sorted({key[0] for key in actual_by_key} | {key[0] for key in expected_by_key})
    per_rule = {}
    for rule_id in rule_ids:
        per_rule[rule_id] = {
            "tp": sum(1 for key in matched_keys if key[0] == rule_id),
            "fp": sum(1 for key in fp_keys if key[0] == rule_id),
            "fn": sum(1 for key in fn_keys if key[0] == rule_id),
        }
    return EvaluationReport(
        expected_count=len(expected_by_key), actual_count=len(actual_by_key),
        tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1,
        false_positives=[{
            "finding_id": actual_by_key[key].finding_id, "rule_id": key[0],
            "entity": key[1], "title": actual_by_key[key].title,
        } for key in fp_keys],
        false_negatives=[expected_by_key[key] for key in fn_keys],
        severity_matches=severity_matches,
        severity_mismatches=severity_mismatches,
        per_rule=per_rule,
    )
