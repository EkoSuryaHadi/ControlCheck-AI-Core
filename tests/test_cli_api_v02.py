import json
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from controlcheck.api import create_app
from controlcheck.cli import app


runner = CliRunner()


def _v02(project_root: Path):
    return (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        project_root / "data" / "controlcheck_golden_expected_findings_v0.2.json",
    )


def test_cli_rejects_incompatible_versions(sample_workbook: Path, project_root: Path, tmp_path: Path):
    catalogue = project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"
    output = tmp_path / "should-not-exist.json"

    result = runner.invoke(app, [
        "run", str(sample_workbook), "--catalogue", str(catalogue), "--output", str(output),
    ])

    assert result.exit_code == 1
    assert "incompatible_artifact_versions" in result.output
    assert not output.exists()


def test_cli_v02_strict_evaluation_writes_extended_report(project_root: Path, tmp_path: Path):
    workbook, catalogue, ground_truth = _v02(project_root)
    output = tmp_path / "evaluation-v02.json"
    result = runner.invoke(app, [
        "evaluate", str(workbook), "--catalogue", str(catalogue),
        "--ground-truth", str(ground_truth), "--output", str(output), "--strict",
    ])

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["precision"] == payload["recall"] == 1.0
    assert payload["severity_accuracy"] == payload["metric_accuracy"] == 1.0


def test_api_returns_structured_version_error(sample_workbook: Path, project_root: Path):
    _, catalogue, _ = _v02(project_root)
    client = TestClient(create_app(catalogue))
    with sample_workbook.open("rb") as source:
        response = client.post(
            "/v1/audits",
            files={"file": ("project.xlsx", source, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "incompatible_artifact_versions"


def test_api_accepts_compatible_v02_workbook(project_root: Path):
    workbook, catalogue, _ = _v02(project_root)
    client = TestClient(create_app(catalogue))
    with workbook.open("rb") as source:
        response = client.post(
            "/v1/audits",
            files={"file": ("golden.xlsx", source, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 200, response.text
    assert response.json()["finding_count"] == 59

