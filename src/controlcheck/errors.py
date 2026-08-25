from __future__ import annotations

from uuid import UUID


class InvalidWorkbookError(ValueError):
    code = "invalid_workbook"
    safe_message = "Workbook could not be parsed"


class ControlCheckApplicationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        analysis_run_id: UUID | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.analysis_run_id = analysis_run_id
