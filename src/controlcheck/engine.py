from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

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
            required_domains = context.definition(rule.rule_id).runtime.required_domains
            blocked_domains = tuple(
                sorted(
                    domain
                    for domain in required_domains
                    if getattr(domain_statuses.get(domain), "value", domain_statuses.get(domain))
                    == "blocked"
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
        findings: list[Finding] = []
        for rule in rules:
            findings.extend(rule.evaluate(dataset, context))
        findings.sort(key=lambda finding: (finding.rule_id, finding.entity_id, finding.finding_id))
        return AuditResult(
            project_id=dataset.project.project_id, data_date=dataset.data_date,
            rule_count=len(rules), finding_count=len(findings), findings=findings,
        )
