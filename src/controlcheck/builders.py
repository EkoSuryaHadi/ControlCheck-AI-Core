from __future__ import annotations

import hashlib

from .config import RuleDefinition
from .models import EvidenceItem, Finding


def normalize_entity(entity_id: str) -> str:
    parts = [part.strip().upper() for part in str(entity_id).split("/") if part.strip()]
    return "/".join(sorted(parts))


def stable_finding_id(rule_id: str, project_id: str, entity_id: str) -> str:
    raw = f"{rule_id}|{project_id}|{normalize_entity(entity_id)}"
    return "FND-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


class FindingBuilder:
    def __init__(self, definition: RuleDefinition):
        self.definition = definition

    def create(self, *, project_id: str, entity_type: str, entity_id: str,
               severity: str, title: str, description: str, metrics: dict,
               evidence: list[EvidenceItem], calculation: dict) -> Finding:
        if not evidence:
            raise ValueError("A finding requires at least one evidence item")
        normalized = normalize_entity(entity_id)
        return Finding(
            finding_id=stable_finding_id(self.definition.code, project_id, normalized),
            rule_id=self.definition.code, rule_name=self.definition.name,
            category=self.definition.category, severity=severity.lower(),
            project_id=project_id, entity_type=entity_type, entity_id=normalized,
            title=title, description=description, metrics=metrics,
            business_impact=self.definition.impact,
            recommendation=self.definition.recommendation,
            evidence=evidence, calculation=calculation,
        )

