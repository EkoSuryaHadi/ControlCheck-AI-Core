from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .config import RuleCatalogue, RuleCatalogueV2, ThresholdConfig
from .models import AuditResult, Finding, ProjectDataset


class RuleLike(Protocol):
    rule_id: str
    def evaluate(self, dataset: ProjectDataset, context: "RuleContext") -> list[Finding]: ...


@dataclass(frozen=True)
class RuleContext:
    catalogue: RuleCatalogue | RuleCatalogueV2 | None
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)

    def definition(self, rule_id: str):
        if self.catalogue is None:
            raise ValueError("Rule catalogue is required")
        return self.catalogue.by_id(rule_id)


class ControlEngine:
    def __init__(self, rules: list[RuleLike] | tuple[RuleLike, ...]):
        ids = [rule.rule_id for rule in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate rule IDs are not allowed")
        self.rules = tuple(sorted(rules, key=lambda rule: rule.rule_id))

    def run(self, dataset: ProjectDataset, context: RuleContext) -> AuditResult:
        findings: list[Finding] = []
        for rule in self.rules:
            findings.extend(rule.evaluate(dataset, context))
        findings.sort(key=lambda finding: (finding.rule_id, finding.entity_id, finding.finding_id))
        return AuditResult(
            project_id=dataset.project.project_id, data_date=dataset.data_date,
            rule_count=len(self.rules), finding_count=len(findings), findings=findings,
        )
