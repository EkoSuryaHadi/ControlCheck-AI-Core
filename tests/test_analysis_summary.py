from datetime import date

from controlcheck.ingestion.mapper import DomainStatus
from controlcheck.models import ProjectDataset, ProjectInfo, ScheduleActivity, SourceRef


def test_schedule_only_dataset_reports_real_schedule_and_no_cost_data():
    from controlcheck.analysis_summary import summarize_dataset

    dataset = ProjectDataset(
        project=ProjectInfo(project_id="MPP-1", project_name="MPP import"),
        data_date=date(2020, 8, 28),
        wbs_nodes=[],
        budgets=[],
        actual_costs=[],
        commitments=[],
        progress=[],
        schedule=[
            ScheduleActivity(
                activity_id="42",
                wbs_code="1.2",
                activity_name="Concrete works",
                discipline=None,
                baseline_start=date(2020, 8, 1),
                baseline_finish=date(2020, 9, 1),
                actual_start=date(2020, 8, 1),
                actual_finish=None,
                planned_progress=0.8,
                actual_progress=0.5,
                total_float_days=24,
                critical=True,
                status="in_progress",
                source=SourceRef(sheet="Schedule", row_number=2),
            )
        ],
    )

    summary = summarize_dataset(
        dataset,
        {domain: DomainStatus.valid for domain in ("wbs", "budget", "actual_cost", "commitments", "schedule", "progress")},
    )

    assert summary["schedule"]["activity_count"] == 1
    assert summary["schedule"]["high_float_count"] == 1
    assert summary["schedule"]["activities"][0]["activity_id"] == "42"
    assert summary["cost"] == {"available": False, "budget_total": 0.0, "actual_total": 0.0, "commitment_total": 0.0}
    assert summary["progress"]["available"] is True
    assert summary["progress"]["source"] == "schedule_derived"
    assert summary["progress"]["actual_progress"] == 0.5
