import json
from pathlib import Path

import pytest

from controlcheck.config import RuleCatalogueV2, load_catalogue
from controlcheck.ground_truth import GroundTruthV2, load_ground_truth
from controlcheck.loader import load_workbook
from controlcheck.versioning import (
    ArtifactVersion,
    VersionCompatibilityError,
    assert_compatible,
)


def _write_v02_catalogue(path: Path) -> Path:
    payload = {
        "version": "0.2",
        "rules": [
            {
                "code": "CST-005",
                "name": "High-Value Transaction Outlier",
                "category": "cost",
                "severity": "warning",
                "objective": "Surface materially large transactions.",
                "inputs": "actual_costs,budgets",
                "logic": "Both materiality thresholds must be met.",
                "threshold": "25% WBS and 3% project budget.",
                "evidence": "Transaction and budget records.",
                "finding": "Transaction requires review.",
                "impact": "Potential coding or commercial anomaly.",
                "recommendation": "Validate the transaction.",
                "false_positive": "Approved exceptions are excluded.",
                "acceptance": "Both thresholds are inclusive.",
                "runtime": {
                    "evaluation_grain": "transaction",
                    "operator": "all_gte",
                    "thresholds": {
                        "wbs_share_min": 0.25,
                        "project_share_min": 0.03
                    },
                    "severity_bands": [
                        {"severity": "warning", "min_value": 0.25},
                        {"severity": "critical", "min_value": 0.50}
                    ],
                    "materiality": {},
                    "exclusions": []
                }
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_artifact_version_normalizes_patch_and_rejects_invalid_values():
    assert ArtifactVersion.parse("v0.2.1").major_minor == "0.2"
    assert ArtifactVersion.parse("0.2").major_minor == "0.2"
    with pytest.raises(ValueError, match="version"):
        ArtifactVersion.parse("latest")


def test_v02_catalogue_requires_structured_runtime_fields(tmp_path: Path):
    catalogue = load_catalogue(_write_v02_catalogue(tmp_path / "catalogue-v02.json"))

    assert isinstance(catalogue, RuleCatalogueV2)
    rule = catalogue.by_id("CST-005")
    assert rule.runtime.evaluation_grain == "transaction"
    assert rule.runtime.thresholds == {
        "wbs_share_min": 0.25,
        "project_share_min": 0.03,
    }


def test_v02_catalogue_rejects_missing_runtime(tmp_path: Path):
    path = _write_v02_catalogue(tmp_path / "catalogue-v02.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["rules"][0]["runtime"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime"):
        load_catalogue(path)


def test_incompatible_dataset_and_catalogue_fail_before_rules():
    with pytest.raises(VersionCompatibilityError, match=r"0\.1.*0\.2"):
        assert_compatible("0.1", "0.2", "0.2")


def test_compatible_versions_allow_patch_differences():
    assert_compatible("0.2.0", "v0.2.3", "0.2")


def test_loader_defaults_historical_workbook_to_v01(sample_workbook: Path):
    dataset = load_workbook(sample_workbook)
    assert dataset.dataset_version == "0.1"


def test_v02_ground_truth_is_strict_and_counted(tmp_path: Path):
    path = tmp_path / "ground-truth-v02.json"
    path.write_text(json.dumps({
        "schema_version": "0.2",
        "dataset_version": "0.2",
        "catalogue_version": "0.2",
        "project_id": "PRJ-1",
        "data_date": "2026-08-15",
        "expected_finding_count": 1,
        "expected_findings": [{
            "expected_id": "EXP-001",
            "rule_id": "CST-005",
            "entity_type": "transaction",
            "entity_id": "ACT-1",
            "severity": "warning",
            "expected_metrics": {"wbs_share": 0.25},
            "rationale": "Inclusive boundary should trigger.",
            "exception_id": None
        }]
    }), encoding="utf-8")

    result = load_ground_truth(path)
    assert isinstance(result, GroundTruthV2)
    assert result.expected_findings[0].entity_id == "ACT-1"

