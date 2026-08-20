-- =============================================================================
-- ControlCheck Persistence Schema v0.3 (Phase 4B Canonical Facts)
-- Executable authority: alembic/versions/20260821_0002_phase4b_canonical_facts.py
-- =============================================================================

CREATE TABLE raw_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_file_id UUID NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    sheet_name VARCHAR(100) NOT NULL,
    row_number INTEGER NOT NULL,
    raw_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_raw_rows_source_location UNIQUE (source_file_id, sheet_name, row_number)
);

CREATE INDEX ix_raw_rows_organization_id ON raw_rows(organization_id);
CREATE INDEX ix_raw_rows_project_id ON raw_rows(project_id);
CREATE INDEX ix_raw_rows_source_file_id ON raw_rows(source_file_id);

CREATE TABLE import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_file_id UUID NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    dataset_snapshot_id UUID REFERENCES dataset_snapshots(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    row_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT ck_import_batches_status CHECK (status IN ('pending','processing','completed','failed'))
);

CREATE INDEX ix_import_batches_organization_id ON import_batches(organization_id);
CREATE INDEX ix_import_batches_project_id ON import_batches(project_id);
CREATE INDEX ix_import_batches_source_file_id ON import_batches(source_file_id);

CREATE TABLE import_column_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sheet_name VARCHAR(100) NOT NULL,
    source_column VARCHAR(100) NOT NULL,
    canonical_field VARCHAR(100) NOT NULL,
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_column_mapping UNIQUE (project_id, sheet_name, source_column)
);

CREATE INDEX ix_import_column_mappings_organization_id ON import_column_mappings(organization_id);
CREATE INDEX ix_import_column_mappings_project_id ON import_column_mappings(project_id);

CREATE TABLE wbs_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_snapshot_id UUID NOT NULL REFERENCES dataset_snapshots(id) ON DELETE CASCADE,
    raw_row_id UUID REFERENCES raw_rows(id) ON DELETE SET NULL,
    wbs_code VARCHAR(80) NOT NULL,
    wbs_name VARCHAR(255) NOT NULL,
    parent_wbs VARCHAR(80),
    discipline VARCHAR(100),
    level INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_wbs_nodes_organization_id ON wbs_nodes(organization_id);
CREATE INDEX ix_wbs_nodes_project_id ON wbs_nodes(project_id);
CREATE INDEX ix_wbs_nodes_dataset_snapshot_id ON wbs_nodes(dataset_snapshot_id);
CREATE INDEX ix_wbs_nodes_wbs_code ON wbs_nodes(wbs_code);

CREATE TABLE budget_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_snapshot_id UUID NOT NULL REFERENCES dataset_snapshots(id) ON DELETE CASCADE,
    raw_row_id UUID REFERENCES raw_rows(id) ON DELETE SET NULL,
    budget_id VARCHAR(100) NOT NULL,
    wbs_code VARCHAR(80),
    cost_code VARCHAR(80),
    description TEXT NOT NULL,
    budget_amount NUMERIC(18, 4) NOT NULL,
    status VARCHAR(50) NOT NULL,
    effective_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_budget_records_organization_id ON budget_records(organization_id);
CREATE INDEX ix_budget_records_project_id ON budget_records(project_id);
CREATE INDEX ix_budget_records_dataset_snapshot_id ON budget_records(dataset_snapshot_id);
CREATE INDEX ix_budget_records_wbs_code ON budget_records(wbs_code);

CREATE TABLE cost_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_snapshot_id UUID NOT NULL REFERENCES dataset_snapshots(id) ON DELETE CASCADE,
    raw_row_id UUID REFERENCES raw_rows(id) ON DELETE SET NULL,
    transaction_id VARCHAR(100) NOT NULL,
    transaction_date DATE NOT NULL,
    wbs_code VARCHAR(80),
    cost_code VARCHAR(80),
    vendor_id VARCHAR(100),
    vendor_name VARCHAR(255),
    po_number VARCHAR(100),
    description TEXT NOT NULL,
    actual_amount NUMERIC(18, 4) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_cost_records_organization_id ON cost_records(organization_id);
CREATE INDEX ix_cost_records_project_id ON cost_records(project_id);
CREATE INDEX ix_cost_records_dataset_snapshot_id ON cost_records(dataset_snapshot_id);
CREATE INDEX ix_cost_records_wbs_code ON cost_records(wbs_code);
CREATE INDEX ix_cost_records_transaction_id ON cost_records(transaction_id);

CREATE TABLE commitment_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_snapshot_id UUID NOT NULL REFERENCES dataset_snapshots(id) ON DELETE CASCADE,
    raw_row_id UUID REFERENCES raw_rows(id) ON DELETE SET NULL,
    commitment_id VARCHAR(100) NOT NULL,
    wbs_code VARCHAR(80),
    po_number VARCHAR(100),
    vendor_id VARCHAR(100),
    vendor_name VARCHAR(255),
    committed_amount NUMERIC(18, 4) NOT NULL,
    invoiced_amount NUMERIC(18, 4) NOT NULL,
    status VARCHAR(50) NOT NULL,
    commitment_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_commitment_records_organization_id ON commitment_records(organization_id);
CREATE INDEX ix_commitment_records_project_id ON commitment_records(project_id);
CREATE INDEX ix_commitment_records_dataset_snapshot_id ON commitment_records(dataset_snapshot_id);
CREATE INDEX ix_commitment_records_wbs_code ON commitment_records(wbs_code);
CREATE INDEX ix_commitment_records_commitment_id ON commitment_records(commitment_id);

CREATE TABLE schedule_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_snapshot_id UUID NOT NULL REFERENCES dataset_snapshots(id) ON DELETE CASCADE,
    raw_row_id UUID REFERENCES raw_rows(id) ON DELETE SET NULL,
    activity_id VARCHAR(100) NOT NULL,
    wbs_code VARCHAR(80),
    activity_name VARCHAR(255) NOT NULL,
    discipline VARCHAR(100),
    baseline_start DATE NOT NULL,
    baseline_finish DATE NOT NULL,
    actual_start DATE,
    actual_finish DATE,
    planned_progress DOUBLE PRECISION NOT NULL,
    actual_progress DOUBLE PRECISION NOT NULL,
    total_float_days INTEGER NOT NULL,
    critical BOOLEAN NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_schedule_activities_organization_id ON schedule_activities(organization_id);
CREATE INDEX ix_schedule_activities_project_id ON schedule_activities(project_id);
CREATE INDEX ix_schedule_activities_dataset_snapshot_id ON schedule_activities(dataset_snapshot_id);
CREATE INDEX ix_schedule_activities_wbs_code ON schedule_activities(wbs_code);
CREATE INDEX ix_schedule_activities_activity_id ON schedule_activities(activity_id);

CREATE TABLE progress_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_snapshot_id UUID NOT NULL REFERENCES dataset_snapshots(id) ON DELETE CASCADE,
    raw_row_id UUID REFERENCES raw_rows(id) ON DELETE SET NULL,
    progress_id VARCHAR(100) NOT NULL,
    period DATE NOT NULL,
    wbs_code VARCHAR(80),
    planned_progress DOUBLE PRECISION NOT NULL,
    actual_progress DOUBLE PRECISION NOT NULL,
    variance DOUBLE PRECISION NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_progress_records_organization_id ON progress_records(organization_id);
CREATE INDEX ix_progress_records_project_id ON progress_records(project_id);
CREATE INDEX ix_progress_records_dataset_snapshot_id ON progress_records(dataset_snapshot_id);
CREATE INDEX ix_progress_records_wbs_code ON progress_records(wbs_code);
CREATE INDEX ix_progress_records_progress_id ON progress_records(progress_id);
