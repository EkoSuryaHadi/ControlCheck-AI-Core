"""API routes for the async heavy-analysis job queue.

Three responsibilities:
1. ``POST /upload-urls`` — hand the browser a presigned PUT URL so large
   workbooks (up to hundreds of MB) go straight to object storage (R2),
   never through the serverless request body.
2. ``POST /analysis-runs/async`` — record the uploaded file as a queued job.
3. ``GET`` job status endpoints — the frontend polls these while the VPS
   Celery worker executes the analysis.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from .api_models import (
    AnalysisJobListResponse,
    AnalysisJobResponse,
    AsyncRunRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from .errors import ControlCheckApplicationError
from .persistence.job_repository import AnalysisJobRepository
from .persistence.repositories import ProjectRepository
from .storage import FileStorage

logger = logging.getLogger(__name__)


def install_job_routes(
    application: FastAPI,
    *,
    require_tenant,
    session_factory: sessionmaker[Session],
    storage: FileStorage,
) -> None:
    @application.post(
        "/v1/projects/{project_id}/upload-urls",
        response_model=UploadUrlResponse,
    )
    def create_upload_url(
        project_id: UUID,
        body: UploadUrlRequest,
        tenant=Depends(require_tenant),
    ) -> UploadUrlResponse:
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)

        safe_name = PurePosixPath(body.filename.replace("\\", "/")).name or "upload.xlsx"
        storage_key = PurePosixPath(str(tenant.organization_id), str(project_id), str(uuid4()), safe_name).as_posix()
        upload_url = storage.presign_put(storage_key, body.content_type, expires_in=900)
        if upload_url is None:
            raise ControlCheckApplicationError(
                "presign_unsupported",
                "This storage backend does not support direct browser uploads",
                501,
            )
        return UploadUrlResponse(upload_url=upload_url, storage_key=storage_key, expires_in=900)

    @application.post(
        "/v1/projects/{project_id}/analysis-runs/async",
        response_model=AnalysisJobResponse,
        status_code=202,
    )
    def create_async_analysis_run(
        project_id: UUID,
        body: AsyncRunRequest,
        tenant=Depends(require_tenant),
    ) -> AnalysisJobResponse:
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)

            if not storage.exists(body.storage_key):
                raise ControlCheckApplicationError(
                    "object_not_found",
                    "Uploaded workbook was not found in storage — presigned upload may have expired",
                    404,
                )

            job = AnalysisJobRepository(session).create_job(
                tenant.organization_id,
                project_id,
                storage_key=body.storage_key,
                filename=body.filename,
                content_type=body.content_type,
                file_size_bytes=body.file_size_bytes,
                workbook_sha256=body.workbook_sha256,
            )
            session.commit()
            session.refresh(job)
        logger.info(
            "Queued analysis job %s for project %s (%s, %d bytes)",
            job.id, project_id, job.filename, job.file_size_bytes,
        )
        return AnalysisJobResponse.model_validate(job)

    @application.get(
        "/v1/projects/{project_id}/analysis-jobs",
        response_model=AnalysisJobListResponse,
    )
    def list_analysis_jobs(
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
        tenant=Depends(require_tenant),
    ) -> AnalysisJobListResponse:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
            jobs, total = AnalysisJobRepository(session).list_jobs(
                tenant.organization_id, project_id, limit=limit, offset=offset
            )
        return AnalysisJobListResponse(
            items=[AnalysisJobResponse.model_validate(j) for j in jobs],
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(jobs) < total),
        )

    @application.get("/v1/analysis-jobs/{job_id}", response_model=AnalysisJobResponse)
    def get_analysis_job(job_id: UUID, tenant=Depends(require_tenant)) -> AnalysisJobResponse:
        with session_factory() as session:
            job = AnalysisJobRepository(session).get_job(tenant.organization_id, job_id)
        if job is None:
            raise ControlCheckApplicationError("analysis_job_not_found", "Analysis job was not found", 404)
        return AnalysisJobResponse.model_validate(job)
