"""Phase 4B canonical ingestion schema.

Revision ID: 20260818_0002
Revises: 20260817_0001
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260818_0002"
down_revision: str | None = "20260817_0001"
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
            sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"),
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
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
            ["raw_rows.dataset_snapshot_id", "raw_rows.id"],
            name=f"fk_{table_name}_snapshot_raw_row",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "wbs_node_id"],
            ["wbs_nodes.dataset_snapshot_id", "wbs_nodes.id"],
            name=f"fk_{table_name}_snapshot_wbs_node",
        ),
    ]


def _create_scoped_indexes(table_name: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table_name}_{column}", table_name, [column])


def upgrade() -> None:
    op.create_table(
        "mapping_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("definition", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version", "sha256", name="uq_mapping_profile_version_hash"),
        sa.CheckConstraint("char_length(sha256) = 64", name="ck_mapping_profile_sha256"),
    )

    op.drop_constraint("ck_dataset_snapshots_status", "dataset_snapshots", type_="check")
    op.alter_column(
        "dataset_snapshots",
        "status",
        existing_type=sa.String(20),
        type_=sa.String(30),
        existing_nullable=False,
        server_default="ingesting",
    )
    op.add_column(
        "dataset_snapshots",
        sa.Column("mapping_profile_version_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column("dataset_snapshots", sa.Column("dedupe_key", sa.String(64)))
    op.add_column(
        "dataset_snapshots",
        sa.Column("row_count_raw", sa.Integer, server_default="0", nullable=False),
    )
    op.add_column(
        "dataset_snapshots",
        sa.Column("row_count_canonical", sa.Integer, server_default="0", nullable=False),
    )
    op.create_foreign_key(
        "fk_snapshots_mapping_profile",
        "dataset_snapshots",
        "mapping_profile_versions",
        ["mapping_profile_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_dataset_snapshots_status",
        "dataset_snapshots",
        "status IN ('ingesting','validated','validated_with_errors','failed')",
    )
    op.create_check_constraint(
        "ck_dataset_snapshots_row_counts",
        "dataset_snapshots",
        "row_count_raw >= 0 AND row_count_canonical >= 0",
    )
    op.create_index(
        "ux_dataset_snapshots_dedupe_key_not_null",
        "dataset_snapshots",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )

    op.create_table(
        "import_batches",
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
            sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "mapping_profile_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mapping_profile_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="ingesting", nullable=False),
        sa.Column("rows_read", sa.Integer, server_default="0", nullable=False),
        sa.Column("rows_valid", sa.Integer, server_default="0", nullable=False),
        sa.Column("rows_warning", sa.Integer, server_default="0", nullable=False),
        sa.Column("rows_rejected", sa.Integer, server_default="0", nullable=False),
        sa.Column("safe_error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.Text),
        sa.Column("error_summary", postgresql.JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("dataset_snapshot_id", name="uq_import_batches_snapshot"),
        sa.UniqueConstraint("dataset_snapshot_id", "id", name="uq_import_batches_snapshot_id"),
        sa.CheckConstraint("status IN ('ingesting','completed','failed')", name="ck_import_batches_status"),
        sa.CheckConstraint(
            "rows_read >= 0 AND rows_valid >= 0 AND rows_warning >= 0 AND rows_rejected >= 0",
            name="ck_import_batches_counts",
        ),
        sa.CheckConstraint(
            "rows_valid + rows_warning + rows_rejected <= rows_read",
            name="ck_import_batches_count_totals",
        ),
    )
    _create_scoped_indexes(
        "import_batches",
        ("organization_id", "project_id", "dataset_snapshot_id", "status"),
    )

    op.add_column(
        "dataset_snapshots",
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_snapshots_snapshot_import_batch",
        "dataset_snapshots",
        "import_batches",
        ["id", "import_batch_id"],
        ["dataset_snapshot_id", "id"],
    )

    op.create_table(
        "dataset_domain_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_tenant_snapshot_columns(),
        sa.Column("domain", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("row_count_raw", sa.Integer, server_default="0", nullable=False),
        sa.Column("row_count_canonical", sa.Integer, server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("warning_count", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "validation_summary",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "domain",
            name="uq_dataset_domain_statuses_snapshot_domain",
        ),
        sa.CheckConstraint("status IN ('valid','warning','blocked')", name="ck_dataset_domain_statuses_status"),
        sa.CheckConstraint(
            "row_count_raw >= 0 AND row_count_canonical >= 0 AND error_count >= 0 AND warning_count >= 0",
            name="ck_dataset_domain_statuses_counts",
        ),
    )
    _create_scoped_indexes(
        "dataset_domain_statuses",
        ("organization_id", "project_id", "dataset_snapshot_id", "status"),
    )

    op.create_table(
        "raw_rows",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        *_tenant_snapshot_columns(),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(30), nullable=False),
        sa.Column("source_sheet", sa.String(100), nullable=False),
        sa.Column("source_row_number", sa.Integer, nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("raw_data", postgresql.JSONB, nullable=False),
        sa.Column("validation_status", sa.String(20), server_default="valid", nullable=False),
        sa.Column(
            "validation_errors",
            postgresql.JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "dataset_snapshot_id",
            "domain",
            "source_row_number",
            name="uq_raw_rows_snapshot_domain_row",
        ),
        sa.UniqueConstraint("dataset_snapshot_id", "id", name="uq_raw_rows_snapshot_id"),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "import_batch_id"],
            ["import_batches.dataset_snapshot_id", "import_batches.id"],
            name="fk_raw_rows_snapshot_import_batch",
        ),
        sa.CheckConstraint("source_row_number > 0", name="ck_raw_rows_source_row_number"),
        sa.CheckConstraint("char_length(row_hash) = 64", name="ck_raw_rows_hash"),
        sa.CheckConstraint(
            "validation_status IN ('valid','warning','invalid')",
            name="ck_raw_rows_validation_status",
        ),
    )
    _create_scoped_indexes(
        "raw_rows",
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
        "wbs_nodes",
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dataset_snapshot_id", "source_key", name="uq_wbs_nodes_snapshot_source_key"),
        sa.UniqueConstraint("raw_row_id", name="uq_wbs_nodes_raw_row_id"),
        sa.UniqueConstraint("dataset_snapshot_id", "id", name="uq_wbs_nodes_snapshot_id"),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "raw_row_id"],
            ["raw_rows.dataset_snapshot_id", "raw_rows.id"],
            name="fk_wbs_nodes_snapshot_raw_row",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_snapshot_id", "parent_id"],
            ["wbs_nodes.dataset_snapshot_id", "wbs_nodes.id"],
            name="fk_wbs_nodes_snapshot_parent",
        ),
        sa.CheckConstraint('"level" >= 1', name="ck_wbs_nodes_level"),
    )
    _create_scoped_indexes(
        "wbs_nodes",
        ("organization_id", "project_id", "dataset_snapshot_id", "raw_row_id"),
    )

    op.create_table(
        "budget_records",
        *_canonical_columns(),
        sa.Column("budget_id", sa.String(300), nullable=False),
        sa.Column("cost_code", sa.String(100)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("budget_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        *_canonical_constraints("budget_records"),
    )
    op.create_table(
        "actual_cost_records",
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
        *_canonical_constraints("actual_cost_records"),
    )
    op.create_table(
        "commitment_records",
        *_canonical_columns(),
        sa.Column("commitment_id", sa.String(300), nullable=False),
        sa.Column("po_number", sa.String(100)),
        sa.Column("vendor_id", sa.String(100)),
        sa.Column("vendor_name", sa.String(250)),
        sa.Column("committed_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("invoiced_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("commitment_date", sa.Date, nullable=False),
        *_canonical_constraints("commitment_records"),
    )
    op.create_table(
        "schedule_activities",
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
        *_canonical_constraints("schedule_activities"),
        sa.CheckConstraint(
            "planned_progress >= 0 AND planned_progress <= 1 AND actual_progress >= 0 AND actual_progress <= 1",
            name="ck_schedule_activities_progress",
        ),
        sa.CheckConstraint("baseline_finish >= baseline_start", name="ck_schedule_activities_baseline_dates"),
        sa.CheckConstraint(
            "actual_finish IS NULL OR actual_start IS NULL OR actual_finish >= actual_start",
            name="ck_schedule_activities_actual_dates",
        ),
    )
    op.create_table(
        "progress_records",
        *_canonical_columns(),
        sa.Column("progress_id", sa.String(300), nullable=False),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("planned_progress", sa.Numeric(7, 4), nullable=False),
        sa.Column("actual_progress", sa.Numeric(7, 4), nullable=False),
        sa.Column("variance", sa.Numeric(7, 4), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        *_canonical_constraints("progress_records"),
        sa.CheckConstraint(
            "planned_progress >= 0 AND planned_progress <= 1 AND actual_progress >= 0 AND actual_progress <= 1",
            name="ck_progress_records_progress",
        ),
        sa.CheckConstraint("variance >= -1 AND variance <= 1", name="ck_progress_records_variance"),
    )
    for table_name in (
        "budget_records",
        "actual_cost_records",
        "commitment_records",
        "schedule_activities",
        "progress_records",
    ):
        _create_scoped_indexes(
            table_name,
            ("organization_id", "project_id", "dataset_snapshot_id", "raw_row_id", "wbs_node_id"),
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
    op.drop_column("finding_evidence", "raw_row_ids")
    op.drop_column("analysis_runs", "skipped_rules")
    op.drop_column("analysis_runs", "executed_rule_ids")

    for table_name in (
        "progress_records",
        "schedule_activities",
        "commitment_records",
        "actual_cost_records",
        "budget_records",
        "wbs_nodes",
        "raw_rows",
        "dataset_domain_statuses",
    ):
        op.drop_table(table_name)

    op.drop_constraint(
        "fk_snapshots_snapshot_import_batch",
        "dataset_snapshots",
        type_="foreignkey",
    )
    op.drop_column("dataset_snapshots", "import_batch_id")
    op.drop_table("import_batches")

    op.drop_index("ux_dataset_snapshots_dedupe_key_not_null", table_name="dataset_snapshots")
    op.drop_constraint("ck_dataset_snapshots_row_counts", "dataset_snapshots", type_="check")
    op.drop_constraint("ck_dataset_snapshots_status", "dataset_snapshots", type_="check")
    op.execute(
        "UPDATE dataset_snapshots "
        "SET status = CASE WHEN status = 'ingesting' THEN 'failed' ELSE 'validated' END "
        "WHERE status IN ('ingesting', 'validated_with_errors')"
    )
    op.drop_constraint(
        "fk_snapshots_mapping_profile",
        "dataset_snapshots",
        type_="foreignkey",
    )
    op.drop_column("dataset_snapshots", "row_count_canonical")
    op.drop_column("dataset_snapshots", "row_count_raw")
    op.drop_column("dataset_snapshots", "dedupe_key")
    op.drop_column("dataset_snapshots", "mapping_profile_version_id")
    op.alter_column(
        "dataset_snapshots",
        "status",
        existing_type=sa.String(30),
        type_=sa.String(20),
        existing_nullable=False,
        server_default="validated",
    )
    op.create_check_constraint(
        "ck_dataset_snapshots_status",
        "dataset_snapshots",
        "status IN ('validated','failed')",
    )
    op.drop_table("mapping_profile_versions")
