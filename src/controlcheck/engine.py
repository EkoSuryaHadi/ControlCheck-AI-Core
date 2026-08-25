from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

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


@dataclass(frozen=True)
class RuleSkip:
    rule_id: str
    reason_code: str
    blocked_domains: tuple[str, ...]


@dataclass(frozen=True)
class EngineExecution:
    audit: AuditResult
    executed_rule_ids: tuple[str, ...]
    skipped_rules: tuple[RuleSkip, ...]


_REQUIRED_DOMAINS_BY_RULE: dict[str, tuple[str, ...]] = {
    "DQ-001": ("wbs", "budget", "actual_cost", "schedule", "progress"),
    "DQ-002": ("actual_cost",),
    "DQ-003": ("schedule", "progress"),
    "DQ-004": (
        "wbs",
        "budget",
        "actual_cost",
        "commitments",
        "schedule",
        "progress",
    ),
    "DQ-005": ("actual_cost",),
    "CST-001": ("wbs", "budget", "actual_cost"),
    "CST-002": ("wbs", "budget", "actual_cost", "commitments"),
    "CST-003": ("wbs", "budget", "actual_cost"),
    "CST-004": ("actual_cost",),
    "CST-005": ("wbs", "budget", "actual_cost"),
    "CST-006": ("wbs", "budget", "actual_cost", "progress"),
    "SCH-001": ("schedule",),
    "SCH-002": ("schedule",),
    "SCH-003": ("schedule",),
    "SCH-004": ("schedule",),
    "SCH-005": ("schedule",),
    "PRG-001": ("wbs", "progress"),
    "PRG-002": ("progress", "schedule"),
    "PRG-003": ("wbs", "budget", "actual_cost", "progress"),
    "XDOM-001": (
        "wbs",
        "budget",
        "actual_cost",
        "commitments",
        "schedule",
        "progress",
    ),
}


class ControlEngine:
    def __init__(self, rules: list[RuleLike] | tuple[RuleLike, ...]):
        ids = [rule.rule_id for rule in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate rule IDs are not allowed")
        self.rules = tuple(sorted(rules, key=lambda rule: rule.rule_id))

    def run(self, dataset: ProjectDataset, context: RuleContext) -> AuditResult:
        return self._run_rules(dataset, context, self.rules)

    def run_gated(
        self,
        dataset: ProjectDataset,
        context: RuleContext,
        domain_statuses: Mapping[str, object],
    ) -> EngineExecution:
        executed: list[RuleLike] = []
        skipped: list[RuleSkip] = []
        for rule in self.rules:
            runtime = getattr(context.definition(rule.rule_id), "runtime", None)
            required_domains = getattr(runtime, "required_domains", ()) or (
                _REQUIRED_DOMAINS_BY_RULE.get(rule.rule_id, ())
            )
            blocked_domains = tuple(
                sorted(
                    domain
                    for domain in required_domains
                    if getattr(
                        domain_statuses.get(domain),
                        "value",
                        domain_statuses.get(domain),
                    )
                    not in {"valid", "warning"}
                )
            )
            if blocked_domains:
                skipped.append(
                    RuleSkip(
                        rule_id=rule.rule_id,
                        reason_code="blocked_required_domain",
                        blocked_domains=blocked_domains,
                    )
                )
            else:
                executed.append(rule)
        audit = self._run_rules(dataset, context, executed)
        return EngineExecution(
            audit=audit,
            executed_rule_ids=tuple(rule.rule_id for rule in executed),
            skipped_rules=tuple(skipped),
        )

    @staticmethod
    def _run_rules(
        dataset: ProjectDataset,
        context: RuleContext,
        rules: tuple[RuleLike, ...] | list[RuleLike],
    ) -> AuditResult:
        logger.info(
            "Starting audit engine run for project %s (data_date: %s, rules: %d)",
            dataset.project.project_id,
            dataset.data_date,
            len(rules),
        )
        findings: list[Finding] = []
        for rule in rules:
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
            len(rules),
        )
        return AuditResult(
            project_id=dataset.project.project_id, data_date=dataset.data_date,
            rule_count=len(rules), finding_count=len(findings), findings=findings,
        )

