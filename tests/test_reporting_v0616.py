from controlcheck.reporting import render_report_pdf


def test_render_report_pdf_contains_valid_pdf_envelope_and_evidence():
    snapshot = {
        "report_name": "Monthly Project Control Report",
        "period": "Aug 2026",
        "generated_at": "2026-08-23T12:00:00+00:00",
        "generated_by_name": "Project Controller",
        "project": {"code": "PRJ-001", "name": "Sample Project"},
        "analysis_run": {"id": "11111111-1111-4111-8111-111111111111"},
        "health": {"overall_score": 82, "score_band": "Healthy", "data_quality_score": 94},
        "summary": {"open_critical": 1, "open_warning": 2, "resolved": 3, "total_findings": 6},
        "findings": [
            {
                "title": "Negative float detected",
                "severity": "critical",
                "status": "open",
                "category": "schedule",
                "rule_id": "SCH-001",
                "description": "Driving activity has negative total float.",
                "recommendation": "Validate logic and prepare recovery plan.",
                "evidence": [
                    {
                        "source_sheet": "Schedule",
                        "source_rows": [42],
                        "fields": {"Activity ID": "A100", "Total Float": -5},
                    }
                ],
            }
        ],
    }

    pdf = render_report_pdf(snapshot)

    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.endswith(b"%%EOF\n")
    assert b"EVIDENCE APPENDIX" in pdf
    assert b"Schedule" in pdf
    assert len(pdf) > 500
