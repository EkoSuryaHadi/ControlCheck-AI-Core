from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import math
from typing import Any

from openpyxl.utils.datetime import from_excel
from pydantic import BaseModel, ValidationError

from ..models import (
    ActualCostRecord,
    BudgetRecord,
    CommitmentRecord,
    ProgressRecord,
    ProjectInfo,
    ScheduleActivity,
    SourceRef,
    WBSNode,
)
from .profile import ColumnProfile, MappingProfileV1
from .types import ExtractedRow, ExtractedWorkbook


class IssueSeverity(str, Enum):
    error = "error"
    warning = "warning"


class DomainStatus(str, Enum):
    valid = "valid"
    warning = "warning"
    blocked = "blocked"


@dataclass(frozen=True)
class RowIssue:
    code: str
    message: str
    field: str | None
    severity: IssueSeverity


CanonicalRecord = (
    WBSNode
    | BudgetRecord
    | ActualCostRecord
    | CommitmentRecord
    | ScheduleActivity
    | ProgressRecord
)


@dataclass(frozen=True)
class CanonicalRowResult:
    domain: str
    source_key: str
    record: CanonicalRecord | None
    issues: tuple[RowIssue, ...]


@dataclass(frozen=True)
class MappedSnapshot:
    project: ProjectInfo | None
    rows_by_domain: dict[str, list[CanonicalRowResult]]
    domain_statuses: dict[str, DomainStatus]
    error_count: int
    warning_count: int


@dataclass(frozen=True)
class _ScalarError(Exception):
    code: str
    message: str


_MODEL_BY_DOMAIN: dict[str, type[BaseModel]] = {
    "wbs": WBSNode,
    "budget": BudgetRecord,
    "actual_cost": ActualCostRecord,
    "commitments": CommitmentRecord,
    "schedule": ScheduleActivity,
    "progress": ProgressRecord,
}

_WBS_DEPENDENT_DOMAINS = frozenset(
    {"budget", "actual_cost", "commitments", "schedule", "progress"}
)


def _issue(
    code: str,
    message: str,
    field: str | None,
    severity: IssueSeverity = IssueSeverity.error,
) -> RowIssue:
    return RowIssue(code=code, message=message, field=field, severity=severity)


def _missing(column: ColumnProfile) -> _ScalarError:
    return _ScalarError(
        "missing_required_value",
        f"{column.target_field} requires a non-empty value",
    )


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise _ScalarError("invalid_decimal", f"{field} is not a valid decimal")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise _ScalarError("invalid_decimal", f"{field} is not a valid decimal") from None
    if not result.is_finite():
        raise _ScalarError("invalid_decimal", f"{field} must be a finite decimal")
    return result


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        raise _ScalarError("invalid_date", f"{field} is not a valid date")
    if isinstance(value, (int, float, Decimal)):
        try:
            converted = from_excel(value)
            return converted.date() if isinstance(converted, datetime) else converted
        except (OverflowError, TypeError, ValueError):
            raise _ScalarError("invalid_date", f"{field} is not a valid Excel date") from None
    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            raise _ScalarError("invalid_date", f"{field} is not a valid ISO date") from None


def _normalize_scalar(
    value: Any,
    column: ColumnProfile,
) -> tuple[Any, list[RowIssue]]:
    field = column.target_field
    if value is None or (isinstance(value, str) and not value.strip()):
        if column.required or not column.nullable:
            raise _missing(column)
        return None, []

    warnings: list[RowIssue] = []
    if column.scalar_type == "string":
        text = str(value).strip()
        if isinstance(value, str) and text != value:
            warnings.append(
                _issue(
                    "normalized_string",
                    f"{field} had surrounding whitespace removed",
                    field,
                    IssueSeverity.warning,
                )
            )
        elif not isinstance(value, str):
            warnings.append(
                _issue(
                    "coerced_string",
                    f"{field} was converted to text",
                    field,
                    IssueSeverity.warning,
                )
            )
        if not text:
            if column.required or not column.nullable:
                raise _missing(column)
            return None, warnings
        return text, warnings

    if column.scalar_type == "date":
        return _date(value, field), warnings

    if column.scalar_type == "decimal":
        percentage_text = isinstance(value, str) and value.strip().endswith("%")
        decimal_value = _decimal(
            value.strip()[:-1] if percentage_text else value,
            field,
        )
        if column.normalization == "percentage_to_decimal":
            if percentage_text:
                decimal_value /= Decimal("100")
                warnings.append(
                    _issue(
                        "coerced_percentage",
                        f"{field} percentage text was converted to a decimal fraction",
                        field,
                        IssueSeverity.warning,
                    )
                )
            return float(decimal_value), warnings
        return decimal_value, warnings

    if column.scalar_type == "integer":
        if isinstance(value, bool):
            raise _ScalarError("invalid_integer", f"{field} is not a valid integer")
        try:
            decimal_value = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError):
            raise _ScalarError("invalid_integer", f"{field} is not a valid integer") from None
        if not decimal_value.is_finite() or decimal_value != decimal_value.to_integral_value():
            raise _ScalarError("invalid_integer", f"{field} is not a whole number")
        if isinstance(value, str):
            warnings.append(
                _issue(
                    "coerced_integer",
                    f"{field} text was converted to an integer",
                    field,
                    IssueSeverity.warning,
                )
            )
        return int(decimal_value), warnings

    if column.scalar_type == "boolean":
        if isinstance(value, bool):
            return value, warnings
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(float(value)) and value in {0, 1}:
                return bool(value), warnings
        if isinstance(value, str):
            normalized = value.strip().casefold()
            choices = {
                "true": True,
                "yes": True,
                "y": True,
                "1": True,
                "false": False,
                "no": False,
                "n": False,
                "0": False,
            }
            if normalized in choices:
                warnings.append(
                    _issue(
                        "coerced_boolean",
                        f"{field} text was converted to a boolean",
                        field,
                        IssueSeverity.warning,
                    )
                )
                return choices[normalized], warnings
        raise _ScalarError("invalid_boolean", f"{field} is not a valid boolean")

    raise _ScalarError("unsupported_scalar_type", f"{field} has an unsupported scalar type")


def _sort_issues(
    issues: list[RowIssue],
    field_order: dict[str, int],
) -> tuple[RowIssue, ...]:
    severity_order = {IssueSeverity.error: 0, IssueSeverity.warning: 1}
    return tuple(
        sorted(
            issues,
            key=lambda issue: (
                severity_order[issue.severity],
                field_order.get(issue.field or "", len(field_order)),
                issue.code,
                issue.message,
            ),
        )
    )


def _map_row(
    row: ExtractedRow,
    profile: MappingProfileV1,
) -> CanonicalRowResult:
    domain_profile = profile.domains[row.domain]
    values: dict[str, Any] = {}
    issues: list[RowIssue] = []
    field_order = {
        column.target_field: index
        for index, column in enumerate(domain_profile.columns.values())
    }
    for column in domain_profile.columns.values():
        try:
            normalized, column_warnings = _normalize_scalar(
                row.values.get(column.source_header), column
            )
            values[column.target_field] = normalized
            issues.extend(column_warnings)
        except _ScalarError as exc:
            issues.append(_issue(exc.code, exc.message, column.target_field))

    if row.domain == "schedule" and not any(
        issue.field in {"baseline_start", "baseline_finish"}
        and issue.severity is IssueSeverity.error
        for issue in issues
    ):
        baseline_start = values.get("baseline_start")
        baseline_finish = values.get("baseline_finish")
        if baseline_start is not None and baseline_finish is not None and baseline_finish < baseline_start:
            issues.append(
                _issue(
                    "contradictory_dates",
                    "baseline_finish must not be earlier than baseline_start",
                    "baseline_finish",
                )
            )

    if row.domain == "wbs" and not any(
        issue.severity is IssueSeverity.error for issue in issues
    ):
        wbs_code = values.get("wbs_code")
        if values.get("parent_wbs") == wbs_code or values.get("level", 0) < 1:
            field = "parent_wbs" if values.get("parent_wbs") == wbs_code else "level"
            issues.append(
                _issue(
                    "invalid_wbs_identity",
                    "WBS identity must have a positive level and cannot parent itself",
                    field,
                )
            )

    ordered_issues = _sort_issues(issues, field_order)
    if any(issue.severity is IssueSeverity.error for issue in ordered_issues):
        return CanonicalRowResult(row.domain, row.source_key, None, ordered_issues)

    values["source"] = SourceRef(
        sheet=row.sheet_name,
        row_number=row.source_row_number,
    )
    try:
        record = _MODEL_BY_DOMAIN[row.domain].model_validate(values)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = first.get("loc", ())
        field = str(location[0]) if location else None
        invalid = _issue(
            "invalid_record",
            f"Canonical {row.domain} record failed model validation",
            field,
        )
        return CanonicalRowResult(
            row.domain,
            row.source_key,
            None,
            _sort_issues([*ordered_issues, invalid], field_order),
        )
    return CanonicalRowResult(row.domain, row.source_key, record, ordered_issues)


def _validate_wbs_rows(
    rows: list[CanonicalRowResult],
    profile: MappingProfileV1,
) -> list[CanonicalRowResult]:
    field_order = {
        column.target_field: index
        for index, column in enumerate(profile.domains["wbs"].columns.values())
    }
    seen: set[str] = set()
    result: list[CanonicalRowResult] = []
    for row in rows:
        if not isinstance(row.record, WBSNode):
            result.append(row)
            continue
        if row.record.wbs_code in seen:
            duplicate = _issue(
                "duplicate_wbs_code",
                f"WBS code {row.record.wbs_code} is duplicated",
                "wbs_code",
            )
            result.append(
                replace(
                    row,
                    record=None,
                    issues=_sort_issues([*row.issues, duplicate], field_order),
                )
            )
            continue
        seen.add(row.record.wbs_code)
        result.append(row)

    canonical_codes = {
        row.record.wbs_code for row in result if isinstance(row.record, WBSNode)
    }
    validated: list[CanonicalRowResult] = []
    for row in result:
        if (
            isinstance(row.record, WBSNode)
            and row.record.parent_wbs is not None
            and row.record.parent_wbs not in canonical_codes
        ):
            invalid_parent = _issue(
                "invalid_wbs_parent",
                f"WBS parent {row.record.parent_wbs} does not exist in the WBS master",
                "parent_wbs",
            )
            validated.append(
                replace(
                    row,
                    record=None,
                    issues=_sort_issues([*row.issues, invalid_parent], field_order),
                )
            )
        else:
            validated.append(row)
    return validated


def _project(values: dict[str, Any]) -> ProjectInfo | None:
    project_id = str(values.get("project_id", "")).strip()
    project_name = str(values.get("project_name", "")).strip()
    if not project_id or not project_name:
        return None
    return ProjectInfo(project_id=project_id, project_name=project_name)


def map_extracted_workbook(
    extracted: ExtractedWorkbook,
    profile: MappingProfileV1,
) -> MappedSnapshot:
    """Normalize governed raw rows into current domain models without persistence."""
    rows_by_domain = {
        domain: [_map_row(row, profile) for row in extracted.rows_by_domain.get(domain, [])]
        for domain in profile.domains
    }
    rows_by_domain["wbs"] = _validate_wbs_rows(rows_by_domain["wbs"], profile)

    template_errors_by_domain = {
        domain: sum(issue.domain == domain for issue in extracted.template_errors)
        for domain in profile.domains
    }
    domain_statuses: dict[str, DomainStatus] = {}
    for domain, rows in rows_by_domain.items():
        if template_errors_by_domain[domain] or any(
            issue.severity is IssueSeverity.error
            for row in rows
            for issue in row.issues
        ):
            domain_statuses[domain] = DomainStatus.blocked
        elif any(row.issues for row in rows):
            domain_statuses[domain] = DomainStatus.warning
        else:
            domain_statuses[domain] = DomainStatus.valid

    if domain_statuses["wbs"] is DomainStatus.blocked:
        for domain in _WBS_DEPENDENT_DOMAINS:
            if domain in domain_statuses:
                domain_statuses[domain] = DomainStatus.blocked

    row_issues = [
        issue
        for rows in rows_by_domain.values()
        for row in rows
        for issue in row.issues
    ]
    return MappedSnapshot(
        project=_project(extracted.project_values),
        rows_by_domain=rows_by_domain,
        domain_statuses=domain_statuses,
        error_count=len(extracted.template_errors)
        + sum(issue.severity is IssueSeverity.error for issue in row_issues),
        warning_count=sum(issue.severity is IssueSeverity.warning for issue in row_issues),
    )


__all__ = [
    "CanonicalRowResult",
    "DomainStatus",
    "IssueSeverity",
    "MappedSnapshot",
    "RowIssue",
    "map_extracted_workbook",
]
