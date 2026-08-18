from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


DomainName = Literal["wbs", "budget", "actual_cost", "commitments", "schedule", "progress"]
ScalarType = Literal["string", "integer", "decimal", "date", "boolean"]


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_header: str
    target_field: str
    scalar_type: ScalarType
    required: bool
    nullable: bool
    normalization: str


class DomainProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet_name: str
    header_row: int
    columns: dict[str, ColumnProfile]


class MappingProfileV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["0.1"]
    domains: dict[DomainName, DomainProfile]


def load_mapping_profile(path: Path | str) -> MappingProfileV1:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return MappingProfileV1.model_validate(payload)


def mapping_profile_sha256(profile: MappingProfileV1) -> str:
    payload = json.dumps(profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

