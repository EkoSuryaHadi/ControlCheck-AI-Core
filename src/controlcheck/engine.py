from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .config import RuleCatalogue, RuleCatalogueV2, ThresholdConfig
from .logging import get_logger
from .models import AuditResult, Finding, ProjectDataset

logger = get_logger("engine")


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
        logger.info(
            "Starting audit engine run for project %s (data_date: %s, rules: %d)",
            dataset.project.project_id,
            dataset.data_date,
            len(self.rules),
        )
        findings: list[Finding] = []
        for rule in self.rules:
            rule_findings = rule.evaluate(dataset, context)
            if rule_findings:
                logger.debug(
                    "Rule %s generated %d finding(s)",
                    rule.rule_id,
                    len(rule_findings),
                )
            findings.extend(rule_findings)
        findings.sort(key=lambda finding: (finding.rule_id, finding.entity_id, finding.finding_id))
        logger.info(
            "Audit engine run completed for project %s: %d total finding(s) across %d rules",
            dataset.project.project_id,
            len(findings),
            len(self.rules),
        )
        return AuditResult(
            project_id=dataset.project.project_id, data_date=dataset.data_date,
            rule_count=len(self.rules), finding_count=len(findings), findings=findings,
        )

