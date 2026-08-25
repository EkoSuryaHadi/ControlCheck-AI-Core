"""Persist health computation availability and coverage.

Revision ID: 20260825_0011
Revises: 20260825_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260825_0011"
down_revision: str | None = "20260825_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("health_snapshots", "overall_score", nullable=True)
    op.alter_column("health_snapshots", "cost_score", nullable=True)
    op.alter_column("health_snapshots", "schedule_score", nullable=True)
    op.alter_column("health_snapshots", "progress_score", nullable=True)
    op.alter_column("health_snapshots", "dq_score", nullable=True)
    op.drop_constraint("ck_health_score_band", "health_snapshots", type_="check")
    op.create_check_constraint(
        "ck_health_score_band",
        "health_snapshots",
        "score_band IN ('Healthy', 'Needs Attention', 'At Risk', 'Critical', 'Partial', 'Not Computed')",
    )
    op.add_column(
        "health_snapshots",
        sa.Column(
            "computation_status",
            sa.String(length=20),
            nullable=False,
            server_default="computed",
        ),
    )
    op.add_column(
        "health_snapshots",
        sa.Column("coverage_ratio", sa.Float(), nullable=False, server_default="1"),
    )
    op.add_column(
        "health_snapshots",
        sa.Column(
            "unavailable_domains",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "ck_health_computation_status",
        "health_snapshots",
        "computation_status IN ('computed', 'partial', 'not_computed')",
    )
    op.create_check_constraint(
        "ck_health_coverage_ratio",
        "health_snapshots",
        "coverage_ratio >= 0 AND coverage_ratio <= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_health_coverage_ratio", "health_snapshots", type_="check")
    op.drop_constraint("ck_health_computation_status", "health_snapshots", type_="check")
    op.drop_column("health_snapshots", "unavailable_domains")
    op.drop_column("health_snapshots", "coverage_ratio")
    op.drop_column("health_snapshots", "computation_status")
    op.execute(
        """
        UPDATE health_snapshots
        SET overall_score = COALESCE(overall_score, 0),
            cost_score = COALESCE(cost_score, 0),
            schedule_score = COALESCE(schedule_score, 0),
            progress_score = COALESCE(progress_score, 0),
            dq_score = COALESCE(dq_score, 0),
            score_band = CASE
                WHEN score_band IN ('Partial', 'Not Computed') THEN 'Critical'
                ELSE score_band
            END
        """
    )
    op.drop_constraint("ck_health_score_band", "health_snapshots", type_="check")
    op.create_check_constraint(
        "ck_health_score_band",
        "health_snapshots",
        "score_band IN ('Healthy', 'Needs Attention', 'At Risk', 'Critical')",
    )
    op.alter_column("health_snapshots", "dq_score", nullable=False)
    op.alter_column("health_snapshots", "progress_score", nullable=False)
    op.alter_column("health_snapshots", "schedule_score", nullable=False)
    op.alter_column("health_snapshots", "cost_score", nullable=False)
    op.alter_column("health_snapshots", "overall_score", nullable=False)
