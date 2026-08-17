from __future__ import annotations

import json
from pathlib import Path

import typer

from .service import run_audit, run_evaluation


app = typer.Typer(no_args_is_help=True, help="Run deterministic ControlCheck project audits.")


def _write_model(path: Path, model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(model.model_dump_json())
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@app.command("run")
def run_command(
    workbook: Path = typer.Argument(..., exists=True, dir_okay=False),
    catalogue: Path = typer.Option(..., "--catalogue", exists=True, dir_okay=False),
    output: Path = typer.Option(Path("findings.json"), "--output"),
):
    """Run all 20 rules and write findings JSON."""
    try:
        result = run_audit(workbook, catalogue)
        _write_model(output, result)
    except Exception as exc:
        typer.echo(f"audit_failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Wrote {result.finding_count} findings to {output}")


@app.command("evaluate")
def evaluate_command(
    workbook: Path = typer.Argument(..., exists=True, dir_okay=False),
    catalogue: Path = typer.Option(..., "--catalogue", exists=True, dir_okay=False),
    ground_truth: Path = typer.Option(..., "--ground-truth", exists=True, dir_okay=False),
    output: Path = typer.Option(Path("evaluation.json"), "--output"),
    strict: bool = typer.Option(False, "--strict", help="Fail unless precision and recall are both 1.0."),
):
    """Evaluate findings against versioned ground truth."""
    try:
        _, report = run_evaluation(workbook, catalogue, ground_truth)
        _write_model(output, report)
    except Exception as exc:
        typer.echo(f"evaluation_failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"TP={report.tp} FP={report.fp} FN={report.fn} precision={report.precision:.3f} recall={report.recall:.3f}")
    if strict and (report.precision < 1.0 or report.recall < 1.0):
        raise typer.Exit(2)


if __name__ == "__main__":
    app()
