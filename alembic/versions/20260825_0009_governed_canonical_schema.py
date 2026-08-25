"""Add governed canonical ingestion beside the homepage schema.

Revision ID: 20260825_0009
Revises: 20260823_0008
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260825_0009"
down_revision: str | None = "20260823_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _tenant_snapshot_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governed_dataset_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def _canonical_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_tenant_snapshot_columns(),
        sa.Column("raw_row_id", sa.BigInteger, nullable=False),
        sa.Column("wbs_node_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_key", sa.String(300), nullable=False),
        sa.Column("wbs_code", sa.String(100)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def _canonical_constraints(table_name: str) -> list[sa.Constraint]:
    return [
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "source_key",
            name=f"uq_{table_name}_snapshot_source_key",
        ),
        sa.UniqueConstraint("raw_row_id", name=f"uq_{table_name}_raw_row_id"),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "raw_row_id"],
            ["governed_raw_rows.dataset_snapshot_id", "governed_raw_rows.id"],
            name=f"fk_{table_name}_snapshot_raw_row",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "wbs_node_id"],
            ["governed_wbs_nodes.dataset_snapshot_id", "governed_wbs_nodes.id"],
            name=f"fk_{table_name}_snapshot_wbs_node",
        ),
    ]


def _create_indexes(table_name: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table_name}_{column}", table_name, [column])


def upgrade() -> None:
    op.create_table(
        "governed_mapping_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("definition", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "version",
            "sha256",
            name="uq_governed_mapping_profile_version_hash",
        ),
        sa.CheckConstraint(
            "char_length(sha256) = 64",
            name="ck_governed_mapping_profile_sha256",
        ),
    )

    op.create_table(
        "governed_dataset_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mapping_profile_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "governed_mapping_profile_versions.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True)),
        sa.Column("dataset_version", sa.String(20), nullable=False),
        sa.Column("data_date", sa.Date, nullable=False),
        sa.Column("source_project_id", sa.String(100), nullable=False),
        sa.Column("source_project_name", sa.Text, nullable=False),
        sa.Column("dedupe_key", sa.String(64)),
        sa.Column("row_count_raw", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "row_count_canonical",
            sa.Integer,
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(30),
            server_default="ingesting",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "id",
            "import_batch_id",
            name="uq_governed_snapshots_import_batch",
        ),
        sa.CheckConstraint(
            "status IN ('ingesting','validated','validated_with_errors','failed')",
            name="ck_governed_snapshots_status",
        ),
        sa.CheckConstraint(
            "row_count_raw >= 0 AND row_count_canonical >= 0",
            name="ck_governed_snapshots_row_counts",
        ),
    )
    op.create_index(
        "ux_governed_snapshots_dedupe_key_not_null",
        "governed_dataset_snapshots",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    _create_indexes(
        "governed_dataset_snapshots",
        ("organization_id", "project_id", "source_file_id", "status"),
    )

    op.create_table(
        "governed_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governed_dataset_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mapping_profile_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "governed_mapping_profile_versions.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default="ingesting",
            nullable=False,
        ),
        sa.Column("rows_read", sa.Integer, server_default="0", nullable=False),
        sa.Column("rows_valid", sa.Integer, server_default="0", nullable=False),
        sa.Column("rows_warning", sa.Integer, server_default="0", nullable=False),
        sa.Column("rows_rejected", sa.Integer, server_default="0", nullable=False),
        sa.Column("safe_error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.Text),
        sa.Column("error_summary", postgresql.JSONB),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            name="uq_governed_import_batches_snapshot",
        ),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "id",
            name="uq_governed_import_batches_snapshot_id",
        ),
        sa.CheckConstraint(
            "status IN ('ingesting','completed','failed')",
            name="ck_governed_import_batches_status",
        ),
        sa.CheckConstraint(
            "rows_read >= 0 AND rows_valid >= 0 AND rows_warning >= 0 AND rows_rejected >= 0",
            name="ck_governed_import_batches_counts",
        ),
        sa.CheckConstraint(
            "rows_valid + rows_warning + rows_rejected <= rows_read",
            name="ck_governed_import_batches_count_totals",
        ),
    )
    _create_indexes(
        "governed_import_batches",
        ("organization_id", "project_id", "dataset_snapshot_id", "status"),
    )
    op.create_foreign_key(
        "fk_governed_snapshots_import_batch",
        "governed_dataset_snapshots",
        "governed_import_batches",
        ["id", "import_batch_id"],
        ["dataset_snapshot_id", "id"],
    )

    op.create_table(
        "governed_dataset_domain_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_tenant_snapshot_columns(),
        sa.Column("domain", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("row_count_raw", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "row_count_canonical",
            sa.Integer,
            server_default="0",
            nullable=False,
        ),
        sa.Column("error_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("warning_count", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "validation_summary",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "domain",
            name="uq_governed_domain_statuses_snapshot_domain",
        ),
        sa.CheckConstraint(
            "status IN ('valid','warning','blocked')",
            name="ck_governed_domain_statuses_status",
        ),
        sa.CheckConstraint(
            "row_count_raw >= 0 AND row_count_canonical >= 0 AND error_count >= 0 AND warning_count >= 0",
            name="ck_governed_domain_statuses_counts",
        ),
    )
    _create_indexes(
        "governed_dataset_domain_statuses",
        ("organization_id", "project_id", "dataset_snapshot_id", "status"),
    )

    op.create_table(
        "governed_raw_rows",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        *_tenant_snapshot_columns(),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(30), nullable=False),
        sa.Column("source_sheet", sa.String(100), nullable=False),
        sa.Column("source_row_number", sa.Integer, nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("raw_data", postgresql.JSONB, nullable=False),
        sa.Column(
            "validation_status",
            sa.String(20),
            server_default="valid",
            nullable=False,
        ),
        sa.Column(
            "validation_errors",
            postgresql.JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "domain",
            "source_sheet",
            "source_row_number",
            name="uq_governed_raw_rows_source_location",
        ),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "id",
            name="uq_governed_raw_rows_snapshot_id",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "import_batch_id"],
            [
                "governed_import_batches.dataset_snapshot_id",
                "governed_import_batches.id",
            ],
            name="fk_governed_raw_rows_snapshot_import_batch",
        ),
        sa.CheckConstraint(
            "source_row_number > 0",
            name="ck_governed_raw_rows_source_row_number",
        ),
        sa.CheckConstraint(
            "char_length(row_hash) = 64",
            name="ck_governed_raw_rows_hash",
        ),
        sa.CheckConstraint(
            "validation_status IN ('valid','warning','invalid')",
            name="ck_governed_raw_rows_validation_status",
        ),
    )
    _create_indexes(
        "governed_raw_rows",
        (
            "organization_id",
            "project_id",
            "dataset_snapshot_id",
            "import_batch_id",
            "domain",
            "validation_status",
        ),
    )

    op.create_table(
        "governed_wbs_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_tenant_snapshot_columns(),
        sa.Column("raw_row_id", sa.BigInteger, nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_key", sa.String(300), nullable=False),
        sa.Column("wbs_code", sa.String(100), nullable=False),
        sa.Column("wbs_name", sa.String(250), nullable=False),
        sa.Column("parent_wbs", sa.String(100)),
        sa.Column("discipline", sa.String(100)),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "source_key",
            name="uq_governed_wbs_nodes_snapshot_source_key",
        ),
        sa.UniqueConstraint(
            "raw_row_id",
            name="uq_governed_wbs_nodes_raw_row_id",
        ),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "id",
            name="uq_governed_wbs_nodes_snapshot_id",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "raw_row_id"],
            ["governed_raw_rows.dataset_snapshot_id", "governed_raw_rows.id"],
            name="fk_governed_wbs_nodes_snapshot_raw_row",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "parent_id"],
            ["governed_wbs_nodes.dataset_snapshot_id", "governed_wbs_nodes.id"],
            name="fk_governed_wbs_nodes_snapshot_parent",
        ),
        sa.CheckConstraint('"level" >= 1', name="ck_governed_wbs_nodes_level"),
    )
    _create_indexes(
        "governed_wbs_nodes",
        ("organization_id", "project_id", "dataset_snapshot_id", "raw_row_id"),
    )

    op.create_table(
        "governed_budget_records",
        *_canonical_columns(),
        sa.Column("budget_id", sa.String(300), nullable=False),
        sa.Column("cost_code", sa.String(100)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("budget_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        *_canonical_constraints("governed_budget_records"),
    )
    op.create_table(
        "governed_actual_cost_records",
        *_canonical_columns(),
        sa.Column("transaction_id", sa.String(300), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("cost_code", sa.String(100)),
        sa.Column("vendor_id", sa.String(100)),
        sa.Column("vendor_name", sa.String(250)),
        sa.Column("po_number", sa.String(100)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("actual_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        *_canonical_constraints("governed_actual_cost_records"),
    )
    op.create_table(
        "governed_commitment_records",
        *_canonical_columns(),
        sa.Column("commitment_id", sa.String(300), nullable=False),
        sa.Column("po_number", sa.String(100)),
        sa.Column("vendor_id", sa.String(100)),
        sa.Column("vendor_name", sa.String(250)),
        sa.Column("committed_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("invoiced_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("commitment_date", sa.Date, nullable=False),
        *_canonical_constraints("governed_commitment_records"),
    )
    op.create_table(
        "governed_schedule_activities",
        *_canonical_columns(),
        sa.Column("activity_id", sa.String(300), nullable=False),
        sa.Column("activity_name", sa.String(500), nullable=False),
        sa.Column("discipline", sa.String(100)),
        sa.Column("baseline_start", sa.Date, nullable=False),
        sa.Column("baseline_finish", sa.Date, nullable=False),
        sa.Column("actual_start", sa.Date),
        sa.Column("actual_finish", sa.Date),
        sa.Column("planned_progress", sa.Numeric(7, 4), nullable=False),
        sa.Column("actual_progress", sa.Numeric(7, 4), nullable=False),
        sa.Column("total_float_days", sa.Integer, nullable=False),
        sa.Column("critical", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        *_canonical_constraints("governed_schedule_activities"),
        sa.CheckConstraint(
            "planned_progress >= 0 AND actual_progress >= 0",
            name="ck_governed_schedule_activities_progress",
        ),
        sa.CheckConstraint(
            "baseline_finish >= baseline_start",
            name="ck_governed_schedule_activities_baseline_dates",
        ),
    )
    op.create_table(
        "governed_progress_records",
        *_canonical_columns(),
        sa.Column("progress_id", sa.String(300), nullable=False),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("planned_progress", sa.Numeric(7, 4), nullable=False),
        sa.Column("actual_progress", sa.Numeric(7, 4), nullable=False),
        sa.Column("variance", sa.Numeric(7, 4), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        *_canonical_constraints("governed_progress_records"),
        sa.CheckConstraint(
            "planned_progress >= 0 AND actual_progress >= 0",
            name="ck_governed_progress_records_progress",
        ),
        sa.CheckConstraint(
            "variance >= -1 AND variance <= 1",
            name="ck_governed_progress_records_variance",
        ),
    )
    for table_name in (
        "governed_budget_records",
        "governed_actual_cost_records",
        "governed_commitment_records",
        "governed_schedule_activities",
        "governed_progress_records",
    ):
        _create_indexes(
            table_name,
            (
                "organization_id",
                "project_id",
                "dataset_snapshot_id",
                "raw_row_id",
                "wbs_node_id",
            ),
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_governed_snapshots_import_batch",
        "governed_dataset_snapshots",
        type_="foreignkey",
    )
    for table_name in (
        "governed_progress_records",
        "governed_schedule_activities",
        "governed_commitment_records",
        "governed_actual_cost_records",
        "governed_budget_records",
        "governed_wbs_nodes",
        "governed_raw_rows",
        "governed_dataset_domain_statuses",
        "governed_import_batches",
        "governed_dataset_snapshots",
        "governed_mapping_profile_versions",
    ):
        op.drop_table(table_name)
