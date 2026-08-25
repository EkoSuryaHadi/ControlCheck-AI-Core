from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from controlcheck.engine import ControlEngine, RuleContext
from controlcheck.models import ProjectDataset, ProjectInfo


class _Rule:
    def __init__(self, rule_id: str):
        self.rule_id = rule_id

    def evaluate(self, dataset, context):
        return []


class _Catalogue:
    def __init__(self, domains_by_rule: dict[str, list[str]]):
        self.domains_by_rule = domains_by_rule

    def by_id(self, rule_id: str):
        return SimpleNamespace(
            runtime=SimpleNamespace(required_domains=self.domains_by_rule[rule_id])
        )


def _dataset() -> ProjectDataset:
    return ProjectDataset(
        project=ProjectInfo(project_id="PRJ", project_name="Project"),
        data_date=date(2026, 8, 25),
        wbs_nodes=[],
        budgets=[],
        actual_costs=[],
        commitments=[],
        schedule=[],
        progress=[],
        dataset_version="0.2",
    )


def test_domain_gating_records_deterministic_skip_provenance() -> None:
    engine = ControlEngine([_Rule("RULE-Z"), _Rule("RULE-A"), _Rule("RULE-M")])
    context = RuleContext(
        catalogue=_Catalogue(
            {
                "RULE-A": ["budget"],
                "RULE-M": ["progress", "schedule"],
                "RULE-Z": ["actual_cost"],
            }
        )
    )

    execution = engine.run_gated(
        _dataset(),
        context,
        {
            "actual_cost": "valid",
            "budget": "valid",
            "progress": "blocked",
            "schedule": "blocked",
        },
    )

    assert execution.executed_rule_ids == ("RULE-A", "RULE-Z")
    assert [item.rule_id for item in execution.skipped_rules] == ["RULE-M"]
    assert execution.skipped_rules[0].reason_code == "blocked_required_domain"
    assert execution.skipped_rules[0].blocked_domains == ("progress", "schedule")
    assert execution.audit.rule_count == 2


def test_healthy_domain_gating_matches_legacy_engine_execution() -> None:
    engine = ControlEngine([_Rule("RULE-B"), _Rule("RULE-A")])
    context = RuleContext(
        catalogue=_Catalogue({"RULE-A": ["budget"], "RULE-B": ["schedule"]})
    )

    legacy = engine.run(_dataset(), context)
    gated = engine.run_gated(
        _dataset(),
        context,
        {"budget": "valid", "schedule": "valid"},
    )

    assert gated.audit == legacy
    assert gated.executed_rule_ids == ("RULE-A", "RULE-B")
    assert gated.skipped_rules == ()
