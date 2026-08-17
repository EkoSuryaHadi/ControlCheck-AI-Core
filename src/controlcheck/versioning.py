from __future__ import annotations

import re
from dataclasses import dataclass


_VERSION_PATTERN = re.compile(r"^[vV]?(\d+)\.(\d+)(?:\.(\d+))?$")


class VersionCompatibilityError(ValueError):
    """Raised when validation artifacts do not share a major/minor version."""

    code = "incompatible_artifact_versions"


@dataclass(frozen=True, order=True)
class ArtifactVersion:
    major: int
    minor: int
    patch: int = 0

    @classmethod
    def parse(cls, value: str) -> "ArtifactVersion":
        match = _VERSION_PATTERN.fullmatch(str(value).strip())
        if not match:
            raise ValueError(f"Invalid artifact version: {value!r}")
        major, minor, patch = match.groups()
        return cls(int(major), int(minor), int(patch or 0))

    @property
    def major_minor(self) -> str:
        return f"{self.major}.{self.minor}"

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def assert_compatible(
    dataset_version: str,
    catalogue_version: str,
    ground_truth_version: str | None = None,
) -> None:
    labelled = {
        "dataset": ArtifactVersion.parse(dataset_version).major_minor,
        "catalogue": ArtifactVersion.parse(catalogue_version).major_minor,
    }
    if ground_truth_version is not None:
        labelled["ground_truth"] = ArtifactVersion.parse(ground_truth_version).major_minor
    if len(set(labelled.values())) != 1:
        details = ", ".join(f"{name}={version}" for name, version in labelled.items())
        raise VersionCompatibilityError(
            f"{VersionCompatibilityError.code}: Incompatible artifact versions: {details}"
        )
