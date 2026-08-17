from pathlib import Path

from controlcheck.config import RuleCatalogueV2, load_catalogue
from controlcheck.engine import RuleContext
from controlcheck.rules import ALL_RULES


def _run_rule(rule_id, dataset, context):
    rule = next(rule for rule in ALL_RULES if rule.rule_id == rule_id)
    return rule.evaluate(dataset, context)


def _v02_context(project_root: Path) -> RuleContext:
    return RuleContext(catalogue=load_catalogue(
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"
    ))


def test_v02_catalogue_has_structured_runtime_for_all_20_rules(project_root: Path):
    catalogue = load_catalogue(
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"
    )

    assert isinstance(catalogue, RuleCatalogueV2)
    assert len(catalogue.rules) == 20
    assert len({rule.code for rule in catalogue.rules}) == 20
    assert all(rule.runtime.operator and rule.runtime.severity_bands for rule in catalogue.rules)


def test_cst005_requires_both_materiality_thresholds(sample_dataset, project_root: Path):
    findings = _run_rule("CST-005", sample_dataset, _v02_context(project_root))

    assert {finding.entity_id for finding in findings} == {"ACT-9006", "ACT-9007"}
    assert all(finding.calculation["formula"].endswith("AND project_share >= threshold") for finding in findings)


def test_prg003_excludes_current_cost_below_project_materiality(sample_dataset, project_root: Path):
    findings = _run_rule("PRG-003", sample_dataset, _v02_context(project_root))

    assert "4.0" not in {finding.entity_id for finding in findings}
    assert {finding.entity_id for finding in findings} == {"3.2", "3.3"}


def test_vendor_concentration_uses_wbs_vendor_identity(sample_dataset, project_root: Path):
    findings = _run_rule("CST-004", sample_dataset, _v02_context(project_root))

    assert findings
    assert all("|" in finding.entity_id for finding in findings)
    assert all(finding.entity_type == "vendor_wbs" for finding in findings)
    assert "3.2|V005" in {finding.entity_id for finding in findings}

