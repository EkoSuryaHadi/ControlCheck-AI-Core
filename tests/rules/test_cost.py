from decimal import Decimal

import pytest

from controlcheck.rules.cost import COST_RULES


def run_rule(rule_id, dataset, context):
    rule = next(rule for rule in COST_RULES if rule.rule_id == rule_id)
    return rule.evaluate(dataset, context)


def with_budget(dataset, wbs_code, amount):
    budgets = [
        record.model_copy(update={"budget_amount": Decimal(str(amount))})
        if record.wbs_code == wbs_code else record
        for record in dataset.budgets
    ]
    return dataset.model_copy(update={"budgets": budgets})


def test_actual_cost_exceeds_budget_and_equal_boundary_does_not(sample_dataset, context):
    actual = sum(x.actual_amount for x in sample_dataset.actual_costs if x.wbs_code == "1.1")
    equal = with_budget(sample_dataset, "1.1", actual)
    exceeded = with_budget(sample_dataset, "1.1", actual - 1)

    assert "1.1" not in {f.entity_id for f in run_rule("CST-001", equal, context)}
    assert "1.1" in {f.entity_id for f in run_rule("CST-001", exceeded, context)}


@pytest.mark.parametrize(("rule_id", "entity"), [
    ("CST-002", "3.2"),
    ("CST-003", "3.3"),
    ("CST-004", "V005"),
    ("CST-005", "ACT-9006"),
    ("CST-006", "3.2"),
])
def test_cost_catalogue_cases(sample_dataset, context, rule_id, entity):
    findings = run_rule(rule_id, sample_dataset, context)
    assert entity in {finding.entity_id for finding in findings}
    assert all(finding.evidence for finding in findings)


def test_high_cost_low_progress_respects_cost_boundary(sample_dataset, context):
    boundary = with_budget(sample_dataset, "3.2", Decimal("20744592500"))
    below = with_budget(sample_dataset, "3.2", Decimal("20744592501"))
    assert "3.2" in {f.entity_id for f in run_rule("CST-006", boundary, context)}
    assert "3.2" not in {f.entity_id for f in run_rule("CST-006", below, context)}
