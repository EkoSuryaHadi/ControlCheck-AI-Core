"""Persist deterministic snapshot analysis and governed evidence lineage.

Revision ID: 20260825_0010
Revises: 20260825_0009
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260825_0010"
down_revision: str | None = "20260825_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("analysis_runs", "dataset_snapshot_id", nullable=True)
    op.add_column(
        "analysis_runs",
        sa.Column(
            "governed_dataset_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governed_dataset_snapshots.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_analysis_runs_governed_dataset_snapshot_id",
        "analysis_runs",
        ["governed_dataset_snapshot_id"],
    )
    op.create_check_constraint(
        "ck_analysis_runs_one_snapshot_contract",
        "analysis_runs",
        "(dataset_snapshot_id IS NULL) <> (governed_dataset_snapshot_id IS NULL)",
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "executed_rule_ids",
            postgresql.JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "skipped_rules",
            postgresql.JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "finding_evidence",
        sa.Column(
            "raw_row_ids",
            postgresql.JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_analysis_runs_one_snapshot_contract",
        "analysis_runs",
        type_="check",
    )
    # The pre-governed analysis schema requires a simplified snapshot FK.
    # Materialize metadata-only compatibility rows before removing the governed
    # FK so completed analysis history remains representable after rollback.
    op.execute(
        sa.text(
            """
            INSERT INTO dataset_snapshots (
                id,
                organization_id,
                project_id,
                source_file_id,
                dataset_version,
                data_date,
                source_project_id,
                status,
                created_at
            )
            SELECT DISTINCT
                snapshot.id,
                snapshot.organization_id,
                snapshot.project_id,
                snapshot.source_file_id,
                snapshot.dataset_version,
                snapshot.data_date,
                snapshot.source_project_id,
                CASE
                    WHEN snapshot.status IN ('validated', 'validated_with_errors')
                    THEN 'validated'
                    ELSE 'failed'
                END,
                snapshot.created_at
            FROM governed_dataset_snapshots AS snapshot
            JOIN analysis_runs AS run
              ON run.governed_dataset_snapshot_id = snapshot.id
            WHERE run.dataset_snapshot_id IS NULL
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE analysis_runs
            SET dataset_snapshot_id = governed_dataset_snapshot_id
            WHERE dataset_snapshot_id IS NULL
              AND governed_dataset_snapshot_id IS NOT NULL
            """
        )
    )
    op.drop_column("finding_evidence", "raw_row_ids")
    op.drop_column("analysis_runs", "skipped_rules")
    op.drop_column("analysis_runs", "executed_rule_ids")
    op.drop_index(
        "ix_analysis_runs_governed_dataset_snapshot_id",
        table_name="analysis_runs",
    )
    op.drop_column("analysis_runs", "governed_dataset_snapshot_id")
    op.alter_column("analysis_runs", "dataset_snapshot_id", nullable=False)
