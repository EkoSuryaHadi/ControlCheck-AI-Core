from pathlib import Path

from controlcheck.config import ThresholdConfig, load_catalogue
from controlcheck.engine import ControlEngine, RuleContext
from controlcheck.ingestion.mapper import DomainStatus
from controlcheck.loader import load_workbook
from controlcheck.rules import ALL_RULES


def _golden_execution(project_root: Path, domain_statuses):
    dataset = load_workbook(
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    )
    catalogue = load_catalogue(
        project_root / "data" / "controlcheck_rule_catalogue_v0.3.json"
    )
    engine = ControlEngine(ALL_RULES)
    context = RuleContext(catalogue=catalogue, thresholds=ThresholdConfig())
    return engine.run_gated(dataset, context, domain_statuses)


def test_only_progress_dependent_rules_skip_when_progress_blocked(project_root: Path):
    execution = _golden_execution(project_root, {"progress": DomainStatus.blocked})

    assert {item.rule_id for item in execution.skipped_rules} == {
        "DQ-001",
        "DQ-003",
        "DQ-004",
        "CST-006",
        "PRG-001",
        "PRG-002",
        "PRG-003",
        "XDOM-001",
    }
    assert "CST-001" in execution.executed_rule_ids
    assert all(
        item.reason_code == "blocked_required_domain"
        and item.blocked_domains == ("progress",)
        for item in execution.skipped_rules
    )


def test_gated_execution_is_sorted_and_counts_only_executed_rules(project_root: Path):
    execution = _golden_execution(
        project_root,
        {"schedule": "blocked", "progress": "blocked"},
    )

    assert execution.executed_rule_ids == tuple(sorted(execution.executed_rule_ids))
    assert execution.skipped_rules == tuple(
        sorted(execution.skipped_rules, key=lambda item: item.rule_id)
    )
    assert execution.audit.rule_count == len(execution.executed_rule_ids)
    assert len(execution.executed_rule_ids) + len(execution.skipped_rules) == 20


def test_gated_execution_with_healthy_domains_matches_legacy_run(project_root: Path):
    dataset = load_workbook(
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    )
    catalogue = load_catalogue(
        project_root / "data" / "controlcheck_rule_catalogue_v0.3.json"
    )
    engine = ControlEngine(ALL_RULES)
    context = RuleContext(catalogue=catalogue, thresholds=ThresholdConfig())

    legacy = engine.run(dataset, context)
    gated = engine.run_gated(dataset, context, {})

    assert gated.audit == legacy
    assert gated.executed_rule_ids == tuple(rule.rule_id for rule in engine.rules)
    assert gated.skipped_rules == ()
