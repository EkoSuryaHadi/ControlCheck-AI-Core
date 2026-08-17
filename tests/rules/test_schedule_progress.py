import pytest

from controlcheck.rules.cross_domain import CROSS_DOMAIN_RULES
from controlcheck.rules.progress import PROGRESS_RULES
from controlcheck.rules.schedule import SCHEDULE_RULES


ALL = SCHEDULE_RULES + PROGRESS_RULES + CROSS_DOMAIN_RULES


def run_rule(rule_id, dataset, context):
    rule = next(rule for rule in ALL if rule.rule_id == rule_id)
    return rule.evaluate(dataset, context)


@pytest.mark.parametrize(("rule_id", "entity"), [
    ("SCH-001", "A2000"), ("SCH-001", "A3020"),
    ("SCH-002", "A1000"), ("SCH-002", "A1010"),
    ("SCH-003", "A3020"), ("SCH-004", "A3040"),
    ("SCH-005", "A3020"), ("PRG-001", "3.2"),
    ("PRG-002", "5.0"), ("XDOM-001", "3.2"),
])
def test_catalogue_cases_are_detected(sample_dataset, context, rule_id, entity):
    findings = run_rule(rule_id, sample_dataset, context)
    assert entity in {finding.entity_id for finding in findings}
    assert all(finding.evidence for finding in findings)


def test_zero_float_is_not_negative(sample_dataset, context):
    activities = [
        activity.model_copy(update={"total_float_days": 0})
        if activity.activity_id == "A3020" else activity
        for activity in sample_dataset.schedule
    ]
    dataset = sample_dataset.model_copy(update={"schedule": activities})
    assert "A3020" not in {f.entity_id for f in run_rule("SCH-005", dataset, context)}


def test_cost_rising_progress_flat_uses_two_latest_periods(sample_dataset, context):
    progress = [
        item.model_copy(update={"actual_progress": 0.60})
        if item.progress_id == "PRG-31-4" else item
        for item in sample_dataset.progress
    ]
    dataset = sample_dataset.model_copy(update={"progress": progress})
    assert "3.1" in {f.entity_id for f in run_rule("PRG-003", dataset, context)}


def test_registry_contains_exactly_20_unique_rule_ids():
    from controlcheck.rules import ALL_RULES

    ids = [rule.rule_id for rule in ALL_RULES]
    assert len(ids) == 20
    assert len(set(ids)) == 20
    assert ids == sorted(ids)
