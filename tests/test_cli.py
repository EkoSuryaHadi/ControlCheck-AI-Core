import json

from typer.testing import CliRunner

from controlcheck.cli import app


runner = CliRunner()


def test_cli_run_writes_valid_json(sample_workbook, sample_catalogue, tmp_path):
    output = tmp_path / "findings.json"
    result = runner.invoke(app, ["run", str(sample_workbook), "--catalogue", str(sample_catalogue), "--output", str(output)])
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["rule_count"] == 20
    assert payload["finding_count"] == len(payload["findings"])


def test_cli_evaluate_reconciles_counts(sample_workbook, sample_catalogue, sample_ground_truth, tmp_path):
    output = tmp_path / "evaluation.json"
    result = runner.invoke(app, ["evaluate", str(sample_workbook), "--catalogue", str(sample_catalogue),
                                 "--ground-truth", str(sample_ground_truth), "--output", str(output)])
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["expected_count"] == 24
    assert payload["tp"] + payload["fn"] == 24
    assert payload["actual_count"] == payload["tp"] + payload["fp"]
