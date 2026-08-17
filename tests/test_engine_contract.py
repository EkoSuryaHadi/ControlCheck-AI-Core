from pathlib import Path

import pytest

from controlcheck.builders import FindingBuilder
from controlcheck.config import RuleDefinition, load_catalogue
from controlcheck.engine import ControlEngine, RuleContext
from controlcheck.loader import load_workbook
from controlcheck.models import EvidenceItem


class StubRule:
    def __init__(self, rule_id: str, entity: str):
        self.rule_id = rule_id
        self.entity = entity

    def evaluate(self, dataset, context):
        definition = RuleDefinition(
            code=self.rule_id,
            name="Stub",
            category="test",
            severity="warning",
            objective="test",
            inputs="test",
            logic="test",
            threshold="test",
            evidence="test",
            finding="test",
            impact="impact",
            recommendation="recommend",
            false_positive="none",
            acceptance="test",
        )
        return [FindingBuilder(definition).create(
            project_id=dataset.project.project_id,
            entity_type="test",
            entity_id=self.entity,
            severity="warning",
            title="Stub",
            description="Stub finding",
            metrics={},
            evidence=[EvidenceItem(source_sheet="Test", record_ids=[self.entity], fields={})],
            calculation={"operator": "stub", "result": True},
        )]


def test_finding_builder_rejects_empty_evidence():
    definition = RuleDefinition(
        code="R-001", name="Test", category="test", severity="warning",
        objective="test", inputs="test", logic="test", threshold="test",
        evidence="test", finding="test", impact="impact",
        recommendation="recommend", false_positive="none", acceptance="test",
    )
    with pytest.raises(ValueError, match="evidence"):
        FindingBuilder(definition).create(
            project_id="P1", entity_type="wbs", entity_id="1.0",
            severity="warning", title="Test", description="Test", metrics={},
            evidence=[], calculation={"result": True},
        )


def test_engine_orders_rules_and_findings_deterministically(sample_workbook: Path):
    dataset = load_workbook(sample_workbook)
    engine = ControlEngine([StubRule("B-001", "z"), StubRule("A-001", "y")])
    context = RuleContext(catalogue=None)

    first = engine.run(dataset, context).model_dump_json()
    second = engine.run(dataset, context).model_dump_json()

    assert first == second
    assert [finding.rule_id for finding in engine.run(dataset, context).findings] == ["A-001", "B-001"]


def test_catalogue_loads_all_20_rules(project_root: Path):
    source = Path(r"C:\Users\USER\Downloads\controlcheck_rule_catalogue_v0.1.json")
    bundled = project_root / "data" / "controlcheck_rule_catalogue_v0.1.json"
    catalogue = load_catalogue(bundled if bundled.exists() else source)

    assert catalogue.version == "0.1"
    assert len(catalogue.rules) == 20
    assert catalogue.by_id("XDOM-001").category == "cross_domain"
