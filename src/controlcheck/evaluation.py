from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict

from .builders import normalize_entity
from .ground_truth import (
    ExpectedFindingV1,
    GroundTruthV1,
    GroundTruthV2,
    load_ground_truth,
)
from .models import Finding


# Historical public aliases remain stable for v0.1 callers and tests.
ExpectedFinding = ExpectedFindingV1
GroundTruth = GroundTruthV1


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    false_negatives: list[ExpectedFindingV1]
    severity_matches: int
    severity_mismatches: list[dict]
    per_rule: dict[str, dict[str, int]]


class EvaluationReportV2(EvalModel):
    schema_version: str = "0.2"
    compatible: bool = True
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
    raw_tp: int
    raw_fp: int
    raw_fn: int
    raw_precision: float
    raw_recall: float
    raw_f1: float
    false_positives: list[dict[str, Any]]
    false_negatives: list[dict[str, Any]]
    approved_exceptions: list[dict[str, Any]]
    severity_matches: int
    severity_mismatches: list[dict[str, Any]]
    severity_accuracy: float
    metric_matches: int
    metric_expectation_count: int
    metric_mismatches: list[dict[str, Any]]
    metric_accuracy: float
    unreviewed_label_count: int
    boundary_case_count: int
    per_rule: dict[str, dict[str, int]]


def _key(rule_id: str, entity: str) -> tuple[str, str]:
    return rule_id.upper(), normalize_entity(entity)


def _scores(actual_keys: set, expected_keys: set) -> tuple[int, int, int, float, float, float]:
    tp = len(actual_keys & expected_keys)
    fp = len(actual_keys - expected_keys)
    fn = len(expected_keys - actual_keys)
    precision = tp / (tp + fp) if tp + fp else (1.0 if not expected_keys else 0.0)
    recall = tp / (tp + fn) if tp + fn else (1.0 if not actual_keys else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return tp, fp, fn, precision, recall, f1


def _evaluate_v1(findings: list[Finding], expected: GroundTruthV1) -> EvaluationReport:
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


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _metric_equal(actual: Any, expectation: Any) -> bool:
    tolerance = Decimal("0")
    expected_value = expectation
    if isinstance(expectation, dict) and "value" in expectation:
        expected_value = expectation["value"]
        tolerance = Decimal(str(expectation.get("tolerance", 0)))
    actual_decimal = _as_decimal(actual)
    expected_decimal = _as_decimal(expected_value)
    if actual_decimal is not None and expected_decimal is not None:
        return abs(actual_decimal - expected_decimal) <= tolerance
    if isinstance(actual, date):
        actual = actual.isoformat()
    return actual == expected_value


def _evaluate_v2(findings: list[Finding], expected: GroundTruthV2) -> EvaluationReportV2:
    actual_by_key = {_key(item.rule_id, item.entity_id): item for item in findings}
    expected_by_key = {item.match_key: item for item in expected.expected_findings}
    raw_keys, raw_expected_keys = set(actual_by_key), set(expected_by_key)
    raw_tp, raw_fp, raw_fn, raw_precision, raw_recall, raw_f1 = _scores(raw_keys, raw_expected_keys)

    exception_keys = {key for key, item in expected_by_key.items() if item.exception_id is not None}
    approved_exception_keys = raw_keys & exception_keys
    effective_actual_keys = raw_keys - approved_exception_keys
    effective_expected_keys = raw_expected_keys - exception_keys
    tp, fp, fn, precision, recall, f1 = _scores(effective_actual_keys, effective_expected_keys)
    matched_keys = effective_actual_keys & effective_expected_keys
    fp_keys = sorted(effective_actual_keys - effective_expected_keys)
    fn_keys = sorted(effective_expected_keys - effective_actual_keys)

    severity_matches = 0
    severity_mismatches = []
    metric_matches = 0
    metric_expectation_count = 0
    metric_mismatches = []
    for key in sorted(matched_keys):
        actual = actual_by_key[key]
        labelled = expected_by_key[key]
        if actual.severity.lower() == labelled.severity.lower():
            severity_matches += 1
        else:
            severity_mismatches.append({
                "rule_id": key[0], "entity": key[1],
                "expected": labelled.severity.lower(), "actual": actual.severity.lower(),
            })
        for metric, expectation in labelled.metric_expectations.items():
            metric_expectation_count += 1
            actual_value = actual.metrics.get(metric)
            if metric in actual.metrics and _metric_equal(actual_value, expectation):
                metric_matches += 1
            else:
                metric_mismatches.append({
                    "rule_id": key[0], "entity": key[1], "metric": metric,
                    "expected": expectation, "actual": actual_value,
                })

    severity_accuracy = severity_matches / len(matched_keys) if matched_keys else 1.0
    metric_accuracy = metric_matches / metric_expectation_count if metric_expectation_count else 1.0
    rule_ids = sorted({key[0] for key in effective_actual_keys | effective_expected_keys})
    per_rule = {
        rule_id: {
            "tp": sum(1 for key in matched_keys if key[0] == rule_id),
            "fp": sum(1 for key in fp_keys if key[0] == rule_id),
            "fn": sum(1 for key in fn_keys if key[0] == rule_id),
        }
        for rule_id in rule_ids
    }
    unreviewed = sum(not item.adjudication_ref.strip() for item in expected.expected_findings)
    unreviewed += len(fp_keys)
    return EvaluationReportV2(
        expected_count=len(effective_expected_keys), actual_count=len(effective_actual_keys),
        tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1,
        raw_tp=raw_tp, raw_fp=raw_fp, raw_fn=raw_fn,
        raw_precision=raw_precision, raw_recall=raw_recall, raw_f1=raw_f1,
        false_positives=[{
            "finding_id": actual_by_key[key].finding_id,
            "rule_id": key[0], "entity": key[1], "title": actual_by_key[key].title,
        } for key in fp_keys],
        false_negatives=[expected_by_key[key].model_dump() for key in fn_keys],
        approved_exceptions=[{
            "rule_id": key[0], "entity": key[1],
            "exception_id": expected_by_key[key].exception_id,
        } for key in sorted(approved_exception_keys)],
        severity_matches=severity_matches,
        severity_mismatches=severity_mismatches,
        severity_accuracy=severity_accuracy,
        metric_matches=metric_matches,
        metric_expectation_count=metric_expectation_count,
        metric_mismatches=metric_mismatches,
        metric_accuracy=metric_accuracy,
        unreviewed_label_count=unreviewed,
        boundary_case_count=len(expected.boundary_cases),
        per_rule=per_rule,
    )


def evaluate(
    findings: list[Finding],
    expected: GroundTruthV1 | GroundTruthV2,
) -> EvaluationReport | EvaluationReportV2:
    if isinstance(expected, GroundTruthV2):
        return _evaluate_v2(findings, expected)
    return _evaluate_v1(findings, expected)
