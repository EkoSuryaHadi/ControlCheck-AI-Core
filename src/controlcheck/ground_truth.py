from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .versioning import ArtifactVersion


class GroundTruthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedFindingV1(GroundTruthModel):
    expected_id: str
    rule_id: str
    category: str
    severity: str
    source: str
    entity: str
    finding_title: str
    why_expected: str


class GroundTruthV1(GroundTruthModel):
    dataset_version: str
    project_id: str
    data_date: date
    expected_finding_count: int
    expected_findings: list[ExpectedFindingV1]


class ExpectedFindingV2(GroundTruthModel):
    expected_id: str
    rule_id: str
    entity_type: str
    entity_id: str
    severity: str
    expected_metrics: dict[str, Any]
    rationale: str
    exception_id: str | None = None


class GroundTruthV2(GroundTruthModel):
    schema_version: str
    dataset_version: str
    catalogue_version: str
    project_id: str
    data_date: date
    expected_finding_count: int
    expected_findings: list[ExpectedFindingV2]


GroundTruth = GroundTruthV1 | GroundTruthV2


def load_ground_truth(path: Path | str) -> GroundTruth:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    schema_version = payload.get("schema_version", "0.1")
    version = ArtifactVersion.parse(schema_version).major_minor
    model = GroundTruthV2 if version == "0.2" else GroundTruthV1
    result = model.model_validate(payload)
    if result.expected_finding_count != len(result.expected_findings):
        raise ValueError("Ground-truth count does not match expected_findings length")
    keys = [
        (item.rule_id.upper(), getattr(item, "entity_id", getattr(item, "entity", "")).upper())
        for item in result.expected_findings
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("Ground truth contains duplicate rule/entity keys")
    return result

