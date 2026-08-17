from __future__ import annotations

from pathlib import Path

from .config import ThresholdConfig, load_catalogue
from .engine import ControlEngine, RuleContext
from .evaluation import evaluate, load_ground_truth
from .loader import load_workbook
from .rules import ALL_RULES
from .versioning import assert_compatible


def run_audit(workbook: Path | str, catalogue: Path | str, thresholds: ThresholdConfig | None = None):
    dataset = load_workbook(workbook)
    loaded_catalogue = load_catalogue(catalogue)
    assert_compatible(dataset.dataset_version, loaded_catalogue.version)
    context = RuleContext(catalogue=loaded_catalogue, thresholds=thresholds or ThresholdConfig())
    return ControlEngine(ALL_RULES).run(dataset, context)


def run_evaluation(workbook: Path | str, catalogue: Path | str, ground_truth: Path | str):
    dataset = load_workbook(workbook)
    loaded_catalogue = load_catalogue(catalogue)
    expected = load_ground_truth(ground_truth)
    expected_catalogue_version = getattr(expected, "catalogue_version", expected.dataset_version)
    assert_compatible(dataset.dataset_version, loaded_catalogue.version, expected.dataset_version)
    assert_compatible(dataset.dataset_version, expected_catalogue_version, expected.dataset_version)
    context = RuleContext(catalogue=loaded_catalogue, thresholds=ThresholdConfig())
    engine = ControlEngine(ALL_RULES)
    audit = engine.run(dataset, context)
    repeated = engine.run(dataset, context)
    report = evaluate(audit.findings, expected).model_copy(update={
        "executed_rule_count": audit.rule_count,
        "deterministic": audit.model_dump_json() == repeated.model_dump_json(),
    })
    return audit, report
