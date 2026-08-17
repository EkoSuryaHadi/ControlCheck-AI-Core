from __future__ import annotations

from pathlib import Path

from .config import ThresholdConfig, load_catalogue
from .engine import ControlEngine, RuleContext
from .evaluation import evaluate, load_ground_truth
from .loader import load_workbook
from .rules import ALL_RULES


def run_audit(workbook: Path | str, catalogue: Path | str, thresholds: ThresholdConfig | None = None):
    dataset = load_workbook(workbook)
    context = RuleContext(catalogue=load_catalogue(catalogue), thresholds=thresholds or ThresholdConfig())
    return ControlEngine(ALL_RULES).run(dataset, context)


def run_evaluation(workbook: Path | str, catalogue: Path | str, ground_truth: Path | str):
    audit = run_audit(workbook, catalogue)
    repeated = run_audit(workbook, catalogue)
    report = evaluate(audit.findings, load_ground_truth(ground_truth)).model_copy(update={
        "executed_rule_count": audit.rule_count,
        "deterministic": audit.model_dump_json() == repeated.model_dump_json(),
    })
    return audit, report
