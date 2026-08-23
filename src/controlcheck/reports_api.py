from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .auth import decode_token
from .errors import ControlCheckApplicationError
from .persistence.database import create_session_factory
from .persistence.models import (
    AnalysisRunRecord,
    FindingEvidenceRecord,
    FindingRecord,
    HealthSnapshotRecord,
    ProjectRecord,
    ReportPackageRecord,
    UserRecord,
)
from .reporting import render_report_pdf


class ReportCreate(BaseModel):
    analysis_run_id: UUID
    report_name: str = Field(min_length=1, max_length=255)
    report_type: str = "monthly"
    period: str = Field(min_length=1, max_length=80)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    analysis_run_id: UUID
    generated_by: UUID | None = None
    report_name: str
    report_type: str
    period: str
    snapshot: dict
    pdf_size_bytes: int
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportResponse]


def install_report_routes(application) -> None:
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("CONTROLCHECK_DATABASE_URL")
    if not database_url:
        return
    session_factory = create_session_factory(database_url)

    def require_identity(authorization: str | None = Header(None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise ControlCheckApplicationError("authentication_required", "Authentication is required", 401)
        try:
            payload = decode_token(authorization[7:].strip())
            if not payload.get("org_id") or not payload.get("sub"):
                raise ValueError("missing identity claims")
            return {
                "organization_id": UUID(payload["org_id"]),
                "user_id": UUID(payload["sub"]),
                "role": payload.get("role"),
            }
        except ControlCheckApplicationError:
            raise
        except Exception as exc:
            raise ControlCheckApplicationError("invalid_token", "Authentication token is invalid or expired", 401) from exc

    def build_snapshot(session, organization_id: UUID, user_id: UUID, project: ProjectRecord, run: AnalysisRunRecord, payload: ReportCreate) -> dict:
        health = session.scalar(
            select(HealthSnapshotRecord).where(
                HealthSnapshotRecord.organization_id == organization_id,
                HealthSnapshotRecord.project_id == project.id,
                HealthSnapshotRecord.analysis_run_id == run.id,
            )
        )
        findings = list(
            session.scalars(
                select(FindingRecord)
                .where(
                    FindingRecord.organization_id == organization_id,
                    FindingRecord.project_id == project.id,
                    FindingRecord.analysis_run_id == run.id,
                )
                .order_by(FindingRecord.detected_at.asc())
            )
        )
        user = session.get(UserRecord, user_id)
        generated_at = datetime.now(timezone.utc)

        finding_payloads: list[dict] = []
        for finding in findings:
            evidence = list(
                session.scalars(
                    select(FindingEvidenceRecord)
                    .where(FindingEvidenceRecord.finding_id == finding.id)
                    .order_by(FindingEvidenceRecord.evidence_order.asc())
                )
            )
            finding_payloads.append(
                {
                    "id": str(finding.id),
                    "rule_id": finding.rule_id,
                    "title": finding.title,
                    "description": finding.description,
                    "category": finding.category,
                    "severity": finding.severity,
                    "status": finding.status,
                    "business_impact": finding.business_impact,
                    "recommendation": finding.recommendation,
                    "resolved_at": finding.resolved_at.isoformat() if finding.resolved_at else None,
                    "evidence": [
                        {
                            "id": str(item.id),
                            "source_sheet": item.source_sheet,
                            "source_rows": item.source_rows,
                            "record_ids": item.record_ids,
                            "fields": item.fields,
                            "aggregation": item.aggregation,
                        }
                        for item in evidence
                    ],
                }
            )

        active = [item for item in findings if item.status not in {"resolved", "dismissed"}]
        summary = {
            "total_findings": len(findings),
            "open_critical": sum(1 for item in active if item.severity == "critical"),
            "open_warning": sum(1 for item in active if item.severity == "warning"),
            "open_observation": sum(1 for item in active if item.severity == "observation"),
            "resolved": sum(1 for item in findings if item.status == "resolved"),
            "dismissed": sum(1 for item in findings if item.status == "dismissed"),
            "evidence_records": sum(len(item["evidence"]) for item in finding_payloads),
        }

        health_payload = {
            "overall_score": round(float(health.overall_score), 1) if health else None,
            "cost_score": round(float(health.cost_score), 1) if health else None,
            "schedule_score": round(float(health.schedule_score), 1) if health else None,
            "progress_score": round(float(health.progress_score), 1) if health else None,
            "data_quality_score": round(float(health.dq_score), 1) if health else None,
            "score_band": health.score_band if health else None,
            "component_breakdown": health.component_breakdown if health else {},
            "key_drivers": health.key_drivers if health else [],
        }

        return {
            "schema_version": "1.0",
            "report_name": payload.report_name,
            "report_type": payload.report_type,
            "period": payload.period,
            "generated_at": generated_at.isoformat(),
            "generated_by": str(user_id),
            "generated_by_name": user.full_name if user and user.full_name else (user.email if user else str(user_id)),
            "project": {
                "id": str(project.id),
                "code": project.code,
                "name": project.name,
                "currency": project.currency,
                "status": project.status,
            },
            "analysis_run": {
                "id": str(run.id),
                "engine_version": run.engine_version,
                "status": run.status,
                "rule_count": run.rule_count,
                "finding_count": run.finding_count,
                "duration_ms": run.duration_ms,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "workbook_sha256": run.workbook_sha256,
            },
            "health": health_payload,
            "summary": summary,
            "findings": finding_payloads,
        }

    @application.get("/v1/projects/{project_id}/reports", response_model=ReportListResponse)
    def list_reports(project_id: UUID, identity: dict = Depends(require_identity)):
        with session_factory() as session:
            items = list(
                session.scalars(
                    select(ReportPackageRecord)
                    .where(
                        ReportPackageRecord.organization_id == identity["organization_id"],
                        ReportPackageRecord.project_id == project_id,
                    )
                    .order_by(ReportPackageRecord.created_at.desc())
                )
            )
            return ReportListResponse(items=[ReportResponse.model_validate(item) for item in items])

    @application.post("/v1/projects/{project_id}/reports", response_model=ReportResponse, status_code=201)
    def create_report(project_id: UUID, payload: ReportCreate, identity: dict = Depends(require_identity)):
        if payload.report_type not in {"monthly", "executive", "cost", "schedule", "progress"}:
            raise ControlCheckApplicationError("invalid_report_type", "Report type is invalid", 422)

        organization_id = identity["organization_id"]
        with session_factory() as session:
            project = session.scalar(
                select(ProjectRecord).where(
                    ProjectRecord.id == project_id,
                    ProjectRecord.organization_id == organization_id,
                )
            )
            if project is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found", 404)

            run = session.scalar(
                select(AnalysisRunRecord).where(
                    AnalysisRunRecord.id == payload.analysis_run_id,
                    AnalysisRunRecord.project_id == project_id,
                    AnalysisRunRecord.organization_id == organization_id,
                )
            )
            if run is None:
                raise ControlCheckApplicationError("analysis_run_not_found", "Analysis run was not found", 404)
            if run.status not in {"succeeded", "completed"}:
                raise ControlCheckApplicationError("analysis_run_not_complete", "Only completed analysis runs can be reported", 409)

            snapshot = build_snapshot(session, organization_id, identity["user_id"], project, run, payload)
            pdf_bytes = render_report_pdf(snapshot)
            report = ReportPackageRecord(
                organization_id=organization_id,
                project_id=project_id,
                analysis_run_id=run.id,
                generated_by=identity["user_id"],
                report_name=payload.report_name.strip(),
                report_type=payload.report_type,
                period=payload.period.strip(),
                snapshot=snapshot,
                pdf_bytes=pdf_bytes,
                pdf_size_bytes=len(pdf_bytes),
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            return ReportResponse.model_validate(report)

    @application.get("/v1/reports/{report_id}", response_model=ReportResponse)
    def get_report(report_id: UUID, identity: dict = Depends(require_identity)):
        with session_factory() as session:
            report = session.scalar(
                select(ReportPackageRecord).where(
                    ReportPackageRecord.id == report_id,
                    ReportPackageRecord.organization_id == identity["organization_id"],
                )
            )
            if report is None:
                raise ControlCheckApplicationError("report_not_found", "Report was not found", 404)
            return ReportResponse.model_validate(report)

    @application.get("/v1/reports/{report_id}/pdf")
    def get_report_pdf(report_id: UUID, identity: dict = Depends(require_identity)):
        with session_factory() as session:
            report = session.scalar(
                select(ReportPackageRecord).where(
                    ReportPackageRecord.id == report_id,
                    ReportPackageRecord.organization_id == identity["organization_id"],
                )
            )
            if report is None:
                raise ControlCheckApplicationError("report_not_found", "Report was not found", 404)
            filename = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in report.report_name).strip("_") or "ControlCheck_Report"
            return Response(
                content=report.pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{filename}.pdf"'},
            )
