"""Align telemetry index names with ORM metadata.

Revision ID: 20260831_0013
Revises: 20260831_0012
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260831_0013"
down_revision: str | None = "20260831_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_RENAMES = (
    ("ix_product_events_org", "ix_product_events_organization_id"),
    ("ix_product_events_user", "ix_product_events_user_id"),
    ("ix_product_events_project", "ix_product_events_project_id"),
    ("ix_product_events_run", "ix_product_events_analysis_run_id"),
    ("ix_product_events_finding", "ix_product_events_finding_id"),
    ("ix_finding_feedback_org", "ix_finding_feedback_organization_id"),
    ("ix_finding_feedback_user", "ix_finding_feedback_user_id"),
    ("ix_finding_feedback_project", "ix_finding_feedback_project_id"),
    ("ix_finding_feedback_run", "ix_finding_feedback_analysis_run_id"),
    ("ix_finding_feedback_finding", "ix_finding_feedback_finding_id"),
)


def upgrade() -> None:
    for old_name, new_name in _RENAMES:
        op.execute(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"')


def downgrade() -> None:
    for old_name, new_name in reversed(_RENAMES):
        op.execute(f'ALTER INDEX "{new_name}" RENAME TO "{old_name}"')
