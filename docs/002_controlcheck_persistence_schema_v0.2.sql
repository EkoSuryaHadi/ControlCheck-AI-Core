-- ControlCheck AI persistence schema v0.2 (Phase 4A)
--
-- Alembic migration 20260817_0001 is the executable authority for this
-- schema. This SQL is a readable PostgreSQL reference and must remain aligned
-- with the migration; it is not the deployment entry point.

CREATE TABLE organizations (
    id uuid PRIMARY KEY,
    name varchar(200) NOT NULL,
    slug varchar(100) NOT NULL UNIQUE,
    status varchar(20) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_organizations_status CHECK (status IN ('active', 'suspended'))
);

CREATE TABLE projects (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    code varchar(80) NOT NULL,
    name varchar(250) NOT NULL,
    currency varchar(3) NOT NULL DEFAULT 'IDR',
    planned_start date,
    planned_finish date,
    status varchar(20) NOT NULL DEFAULT 'planning',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_projects_org_code UNIQUE (organization_id, code),
    CONSTRAINT ck_projects_status CHECK (status IN ('planning', 'active', 'on_hold', 'completed', 'closed')),
    CONSTRAINT ck_projects_dates CHECK (planned_finish IS NULL OR planned_start IS NULL OR planned_finish >= planned_start)
);

CREATE TABLE source_files (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_name varchar(255) NOT NULL,
    storage_key text NOT NULL,
    mime_type varchar(100) NOT NULL,
    file_size_bytes integer NOT NULL CHECK (file_size_bytes >= 0),
    sha256 varchar(64) NOT NULL CHECK (char_length(sha256) = 64),
    uploaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dataset_snapshots (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_file_id uuid NOT NULL REFERENCES source_files(id) ON DELETE RESTRICT,
    dataset_version varchar(20) NOT NULL,
    data_date date NOT NULL,
    source_project_id varchar(100) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'validated' CHECK (status IN ('validated', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rule_catalogue_versions (
    id uuid PRIMARY KEY,
    version varchar(20) NOT NULL,
    sha256 varchar(64) NOT NULL CHECK (char_length(sha256) = 64),
    definition jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_catalogue_version_hash UNIQUE (version, sha256)
);

CREATE TABLE analysis_runs (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_snapshot_id uuid NOT NULL REFERENCES dataset_snapshots(id) ON DELETE RESTRICT,
    catalogue_version_id uuid NOT NULL REFERENCES rule_catalogue_versions(id) ON DELETE RESTRICT,
    engine_version varchar(20) NOT NULL,
    workbook_sha256 varchar(64) NOT NULL CHECK (char_length(workbook_sha256) = 64),
    status varchar(20) NOT NULL DEFAULT 'running' CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    rule_count integer NOT NULL DEFAULT 0,
    finding_count integer NOT NULL DEFAULT 0,
    duration_ms integer,
    safe_error_code varchar(80),
    safe_error_message text,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (rule_count >= 0 AND finding_count >= 0),
    CHECK (duration_ms IS NULL OR duration_ms >= 0)
);

CREATE TABLE findings (
    id uuid PRIMARY KEY,
    analysis_run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    engine_finding_id varchar(64) NOT NULL,
    rule_id varchar(40) NOT NULL,
    rule_name varchar(200) NOT NULL,
    entity_type varchar(40) NOT NULL,
    entity_id varchar(300) NOT NULL,
    category varchar(40) NOT NULL,
    severity varchar(20) NOT NULL CHECK (severity IN ('critical', 'warning', 'observation')),
    status varchar(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
    title varchar(300) NOT NULL,
    description text NOT NULL,
    metrics jsonb NOT NULL,
    calculation jsonb NOT NULL,
    business_impact text NOT NULL,
    recommendation text NOT NULL,
    confidence numeric(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    detected_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    CONSTRAINT uq_findings_run_engine_id UNIQUE (analysis_run_id, engine_finding_id)
);

CREATE TABLE finding_evidence (
    id uuid PRIMARY KEY,
    finding_id uuid NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    evidence_order integer NOT NULL,
    source_sheet varchar(100) NOT NULL,
    source_rows jsonb NOT NULL,
    record_ids jsonb NOT NULL,
    fields jsonb NOT NULL,
    aggregation jsonb,
    CONSTRAINT uq_evidence_order UNIQUE (finding_id, evidence_order)
);

CREATE TABLE approved_exceptions (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE,
    rule_id varchar(40) NOT NULL,
    entity_type varchar(40),
    entity_id varchar(300),
    rationale text NOT NULL,
    approver_reference varchar(200) NOT NULL,
    evidence_reference text NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'revoked')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE audit_logs (
    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id uuid REFERENCES projects(id) ON DELETE SET NULL,
    event_type varchar(100) NOT NULL,
    entity_type varchar(80),
    entity_id varchar(100),
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Tenant, lifecycle, lookup, and evidence indexes are created by Alembic.
