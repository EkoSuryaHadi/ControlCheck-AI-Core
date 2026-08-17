import pytest

from controlcheck.rules.data_quality import DATA_QUALITY_RULES


def run_rule(rule_id, dataset, context):
    rule = next(rule for rule in DATA_QUALITY_RULES if rule.rule_id == rule_id)
    return rule.evaluate(dataset, context)


@pytest.mark.parametrize(("rule_id", "entity"), [
    ("DQ-001", "ACT-9003"),
    ("DQ-002", "ACT-9001/ACT-9002"),
    ("DQ-003", "A9990"),
    ("DQ-004", "ACT-9004"),
    ("DQ-005", "ACT-9005"),
])
def test_data_quality_planted_cases(sample_dataset, context, rule_id, entity):
    findings = run_rule(rule_id, sample_dataset, context)
    assert entity in {finding.entity_id for finding in findings}
    assert all(finding.evidence and finding.calculation for finding in findings)


def test_missing_and_orphan_wbs_are_distinct(sample_dataset, context):
    missing = {f.entity_id for f in run_rule("DQ-001", sample_dataset, context)}
    orphan = {f.entity_id for f in run_rule("DQ-004", sample_dataset, context)}
    assert "ACT-9003" in missing and "ACT-9003" not in orphan
    assert "ACT-9004" in orphan and "ACT-9004" not in missing
