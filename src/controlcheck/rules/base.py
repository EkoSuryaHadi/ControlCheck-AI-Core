from __future__ import annotations

from typing import Any, Protocol

from ..builders import FindingBuilder
from ..config import RuleDefinition
from ..engine import RuleContext
from ..models import EvidenceItem, Finding, ProjectDataset, SourceRef


class Rule(Protocol):
    rule_id: str
    def evaluate(self, dataset: ProjectDataset, context: RuleContext) -> list[Finding]: ...


class BaseRule:
    rule_id: str

    def finding(self, dataset: ProjectDataset, context: RuleContext, *,
                entity_type: str, entity_id: str, severity: str | None = None,
                title: str | None = None, description: str,
                metrics: dict[str, Any], evidence: list[EvidenceItem],
                calculation: dict[str, Any]) -> Finding:
        definition = context.definition(self.rule_id)
        return FindingBuilder(definition).create(
            project_id=dataset.project.project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            severity=severity or definition.severity,
            title=title or definition.name,
            description=description,
            metrics=metrics,
            evidence=evidence,
            calculation=calculation,
        )


def runtime_threshold(context: RuleContext, rule_id: str, name: str, fallback: Any) -> Any:
    runtime = getattr(context.definition(rule_id), "runtime", None)
    return runtime.thresholds.get(name, fallback) if runtime is not None else fallback


def runtime_materiality(context: RuleContext, rule_id: str, name: str, fallback: Any) -> Any:
    runtime = getattr(context.definition(rule_id), "runtime", None)
    return runtime.materiality.get(name, fallback) if runtime is not None else fallback


def row_evidence(sheet: str, record_id: str, source: SourceRef,
                 fields: dict[str, Any]) -> EvidenceItem:
    return EvidenceItem(source_sheet=sheet, source_rows=[source.row_number],
                        record_ids=[record_id], fields=fields)
