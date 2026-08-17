-- ControlCheck AI - Core PostgreSQL schema v0.1
-- Run on PostgreSQL 15+ (uuid-ossp not required; uses gen_random_uuid from pgcrypto)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(200) NOT NULL,
  slug VARCHAR(100) NOT NULL UNIQUE,
  status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(320) NOT NULL UNIQUE,
  full_name VARCHAR(200) NOT NULL,
  password_hash TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','invited','disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organization_members (
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(30) NOT NULL CHECK (role IN ('owner','admin','manager','analyst','viewer')),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active BOOLEAN NOT NULL DEFAULT true,
  PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  code VARCHAR(80) NOT NULL,
  name VARCHAR(250) NOT NULL,
  client_name VARCHAR(250),
  project_type VARCHAR(80) CHECK (project_type IN ('EPC','construction','oil_gas','mining','other')),
  currency CHAR(3) NOT NULL DEFAULT 'IDR',
  planned_start DATE,
  planned_finish DATE,
  status VARCHAR(30) NOT NULL DEFAULT 'planning'
    CHECK (status IN ('planning','active','on_hold','completed','closed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, code),
  CHECK (planned_finish IS NULL OR planned_start IS NULL OR planned_finish >= planned_start)
);

CREATE TABLE project_members (
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(30) NOT NULL CHECK (role IN ('manager','analyst','viewer')),
  is_active BOOLEAN NOT NULL DEFAULT true,
  PRIMARY KEY (project_id, user_id)
);

CREATE TABLE source_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  file_name VARCHAR(255) NOT NULL,
  storage_key TEXT NOT NULL,
  mime_type VARCHAR(100) NOT NULL,
  file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
  sha256 CHAR(64) NOT NULL,
  uploaded_by UUID NOT NULL REFERENCES users(id),
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE datasets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_file_id UUID REFERENCES source_files(id) ON DELETE SET NULL,
  dataset_type VARCHAR(30) NOT NULL CHECK (dataset_type IN ('budget','actual_cost','schedule','progress','commitment','other')),
  name VARCHAR(150) NOT NULL,
  schema_version VARCHAR(20) NOT NULL DEFAULT '1.0',
  status VARCHAR(20) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','mapped','validated','imported','failed')),
  record_count INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE import_batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  status VARCHAR(20) NOT NULL DEFAULT 'running'
    CHECK (status IN ('running','success','partial','failed')),
  rows_read INTEGER NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
  rows_valid INTEGER NOT NULL DEFAULT 0 CHECK (rows_valid >= 0),
  rows_rejected INTEGER NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
  error_summary JSONB,
  CHECK (rows_valid + rows_rejected <= rows_read)
);

CREATE TABLE import_column_mappings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  source_column VARCHAR(200) NOT NULL,
  canonical_field VARCHAR(100) NOT NULL,
  data_type VARCHAR(30) NOT NULL CHECK (data_type IN ('string','date','decimal','integer','boolean')),
  mapping_method VARCHAR(20) NOT NULL CHECK (mapping_method IN ('manual','rule','ai')),
  confidence NUMERIC(5,4) CHECK (confidence >= 0 AND confidence <= 1),
  is_confirmed BOOLEAN NOT NULL DEFAULT false,
  UNIQUE (dataset_id, source_column)
);

CREATE TABLE raw_rows (
  id BIGSERIAL PRIMARY KEY,
  import_batch_id UUID NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
  source_row_number INTEGER NOT NULL CHECK (source_row_number > 0),
  row_hash CHAR(64) NOT NULL,
  raw_data JSONB NOT NULL,
  validation_status VARCHAR(20) NOT NULL DEFAULT 'valid'
    CHECK (validation_status IN ('valid','warning','rejected')),
  validation_errors JSONB,
  UNIQUE (import_batch_id, source_row_number)
);

CREATE TABLE wbs_nodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  parent_id UUID REFERENCES wbs_nodes(id) ON DELETE SET NULL,
  wbs_code VARCHAR(100) NOT NULL,
  wbs_name VARCHAR(250),
  level_no INTEGER NOT NULL CHECK (level_no >= 1),
  path TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (project_id, wbs_code)
);

CREATE TABLE budget_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  wbs_node_id UUID REFERENCES wbs_nodes(id) ON DELETE SET NULL,
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
  raw_row_id BIGINT REFERENCES raw_rows(id) ON DELETE SET NULL,
  cost_code VARCHAR(100),
  period DATE,
  budget_amount NUMERIC(20,2) NOT NULL CHECK (budget_amount >= 0),
  approved_budget_amount NUMERIC(20,2) CHECK (approved_budget_amount IS NULL OR approved_budget_amount >= 0),
  currency CHAR(3) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cost_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  wbs_node_id UUID REFERENCES wbs_nodes(id) ON DELETE SET NULL,
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
  raw_row_id BIGINT REFERENCES raw_rows(id) ON DELETE SET NULL,
  transaction_date DATE NOT NULL,
  cost_code VARCHAR(100),
  vendor_name VARCHAR(250),
  vendor_code VARCHAR(100),
  po_number VARCHAR(100),
  document_number VARCHAR(100),
  description TEXT,
  amount NUMERIC(20,2) NOT NULL CHECK (amount >= 0),
  cost_type VARCHAR(30) CHECK (cost_type IN ('actual','commitment','accrual','invoice','other')),
  currency CHAR(3) NOT NULL
);

CREATE TABLE schedule_activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  wbs_node_id UUID REFERENCES wbs_nodes(id) ON DELETE SET NULL,
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
  raw_row_id BIGINT REFERENCES raw_rows(id) ON DELETE SET NULL,
  activity_code VARCHAR(100) NOT NULL,
  activity_name VARCHAR(500) NOT NULL,
  baseline_start DATE,
  baseline_finish DATE,
  actual_start DATE,
  actual_finish DATE,
  planned_progress NUMERIC(7,4) CHECK (planned_progress IS NULL OR planned_progress BETWEEN 0 AND 1),
  actual_progress NUMERIC(7,4) CHECK (actual_progress IS NULL OR actual_progress BETWEEN 0 AND 1),
  total_float_days INTEGER,
  critical_flag BOOLEAN,
  status VARCHAR(30) CHECK (status IN ('not_started','in_progress','completed','delayed','cancelled')),
  UNIQUE (project_id, activity_code),
  CHECK (baseline_finish IS NULL OR baseline_start IS NULL OR baseline_finish >= baseline_start),
  CHECK (actual_finish IS NULL OR actual_start IS NULL OR actual_finish >= actual_start)
);

CREATE TABLE progress_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  wbs_node_id UUID REFERENCES wbs_nodes(id) ON DELETE SET NULL,
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
  raw_row_id BIGINT REFERENCES raw_rows(id) ON DELETE SET NULL,
  period DATE NOT NULL,
  planned_progress NUMERIC(7,4) NOT NULL CHECK (planned_progress BETWEEN 0 AND 1),
  actual_progress NUMERIC(7,4) NOT NULL CHECK (actual_progress BETWEEN 0 AND 1),
  progress_method VARCHAR(50),
  UNIQUE (project_id, wbs_node_id, period)
);

CREATE TABLE control_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(80) NOT NULL UNIQUE,
  name VARCHAR(200) NOT NULL,
  category VARCHAR(30) NOT NULL CHECK (category IN ('data_quality','cost','schedule','progress','cross_domain')),
  severity_default VARCHAR(20) NOT NULL CHECK (severity_default IN ('critical','warning','observation')),
  version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
  expression JSONB NOT NULL,
  explanation_template TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE control_rule_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  rule_id UUID NOT NULL REFERENCES control_rules(id) ON DELETE RESTRICT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  status VARCHAR(20) NOT NULL DEFAULT 'running' CHECK (status IN ('running','success','failed')),
  records_scanned INTEGER NOT NULL DEFAULT 0 CHECK (records_scanned >= 0),
  findings_created INTEGER NOT NULL DEFAULT 0 CHECK (findings_created >= 0),
  execution_ms INTEGER CHECK (execution_ms IS NULL OR execution_ms >= 0)
);

CREATE TABLE findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  rule_run_id UUID REFERENCES control_rule_runs(id) ON DELETE SET NULL,
  rule_id UUID REFERENCES control_rules(id) ON DELETE SET NULL,
  category VARCHAR(30) NOT NULL CHECK (category IN ('data_quality','cost','schedule','progress','cross_domain')),
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical','warning','observation')),
  status VARCHAR(20) NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','acknowledged','in_progress','resolved','dismissed')),
  title VARCHAR(300) NOT NULL,
  description TEXT NOT NULL,
  metric_json JSONB,
  impact_amount NUMERIC(20,2),
  confidence NUMERIC(5,4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  wbs_node_id UUID REFERENCES wbs_nodes(id) ON DELETE SET NULL,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  resolution_note TEXT
);

CREATE TABLE finding_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
  raw_row_id BIGINT REFERENCES raw_rows(id) ON DELETE SET NULL,
  entity_type VARCHAR(50) CHECK (entity_type IN ('budget','cost','schedule','progress','wbs')),
  entity_id UUID,
  evidence_role VARCHAR(30) NOT NULL CHECK (evidence_role IN ('primary','supporting','context')),
  excerpt JSONB
);

CREATE TABLE actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  finding_id UUID REFERENCES findings(id) ON DELETE SET NULL,
  title VARCHAR(300) NOT NULL,
  description TEXT,
  priority VARCHAR(20) NOT NULL CHECK (priority IN ('high','medium','low')),
  owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  due_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','done','cancelled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE health_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  snapshot_date DATE NOT NULL,
  overall_score NUMERIC(6,2) NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
  cost_score NUMERIC(6,2) NOT NULL CHECK (cost_score BETWEEN 0 AND 100),
  schedule_score NUMERIC(6,2) NOT NULL CHECK (schedule_score BETWEEN 0 AND 100),
  progress_score NUMERIC(6,2) NOT NULL CHECK (progress_score BETWEEN 0 AND 100),
  data_quality_score NUMERIC(6,2) NOT NULL CHECK (data_quality_score BETWEEN 0 AND 100),
  score_version VARCHAR(20) NOT NULL,
  details JSONB,
  UNIQUE (project_id, snapshot_date, score_version)
);

CREATE TABLE ai_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(250),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ai_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL CHECK (role IN ('user','assistant','system','tool')),
  content TEXT,
  tool_name VARCHAR(100),
  tool_payload JSONB,
  evidence_refs JSONB,
  model VARCHAR(100),
  input_tokens INTEGER CHECK (input_tokens IS NULL OR input_tokens >= 0),
  output_tokens INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  requested_by UUID NOT NULL REFERENCES users(id),
  report_type VARCHAR(30) NOT NULL CHECK (report_type IN ('monthly','executive','findings','data_quality','custom')),
  period_start DATE,
  period_end DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','generating','ready','failed')),
  storage_key TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  event_type VARCHAR(100) NOT NULL,
  entity_type VARCHAR(80),
  entity_id VARCHAR(100),
  metadata JSONB,
  ip_address INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Performance indexes
CREATE INDEX idx_projects_org_status ON projects(organization_id, status);
CREATE INDEX idx_project_members_user ON project_members(user_id, is_active);
CREATE INDEX idx_source_files_project ON source_files(project_id, uploaded_at DESC);
CREATE INDEX idx_datasets_project_type ON datasets(project_id, dataset_type, created_at DESC);
CREATE INDEX idx_import_batches_dataset ON import_batches(dataset_id, started_at DESC);
CREATE INDEX idx_raw_rows_batch_status ON raw_rows(import_batch_id, validation_status);
CREATE INDEX idx_wbs_project_parent ON wbs_nodes(project_id, parent_id);
CREATE INDEX idx_budget_project_wbs_period ON budget_records(project_id, wbs_node_id, period);
CREATE INDEX idx_cost_project_date ON cost_records(project_id, transaction_date);
CREATE INDEX idx_cost_project_wbs ON cost_records(project_id, wbs_node_id);
CREATE INDEX idx_cost_project_po ON cost_records(project_id, po_number);
CREATE INDEX idx_cost_project_vendor ON cost_records(project_id, vendor_code);
CREATE INDEX idx_schedule_project_finish ON schedule_activities(project_id, baseline_finish);
CREATE INDEX idx_schedule_project_critical ON schedule_activities(project_id, critical_flag);
CREATE INDEX idx_schedule_project_status ON schedule_activities(project_id, status);
CREATE INDEX idx_progress_project_period ON progress_records(project_id, period);
CREATE INDEX idx_rules_category_active ON control_rules(category, is_active);
CREATE INDEX idx_rule_runs_project_status ON control_rule_runs(project_id, status, started_at DESC);
CREATE INDEX idx_findings_project_status_severity ON findings(project_id, status, severity);
CREATE INDEX idx_findings_project_category ON findings(project_id, category);
CREATE INDEX idx_findings_project_detected ON findings(project_id, detected_at DESC);
CREATE INDEX idx_evidence_finding ON finding_evidence(finding_id);
CREATE INDEX idx_actions_project_status ON actions(project_id, status);
CREATE INDEX idx_health_project_date ON health_snapshots(project_id, snapshot_date DESC);
CREATE INDEX idx_ai_conversations_project ON ai_conversations(project_id, created_at DESC);
CREATE INDEX idx_ai_messages_conversation ON ai_messages(conversation_id, created_at);
CREATE INDEX idx_reports_project_status ON reports(project_id, status, created_at DESC);
CREATE INDEX idx_audit_org_date ON audit_logs(organization_id, created_at DESC);
CREATE INDEX idx_audit_project_date ON audit_logs(project_id, created_at DESC);

-- Seed control rules
INSERT INTO control_rules (code, name, category, severity_default, expression, explanation_template) VALUES
('DQ-001','Missing WBS in cost data','data_quality','warning','{"type":"missing","dataset":"actual_cost","field":"wbs_code"}','Cost rows are missing WBS mapping; review source data or mapping.'),
('DQ-002','Duplicate transaction/document','data_quality','warning','{"type":"duplicate","dataset":"actual_cost","keys":["document_number","amount","transaction_date"]}','Potential duplicate cost transaction detected.'),
('DQ-003','Invalid date / finish before start','data_quality','critical','{"type":"date_consistency","dataset":"schedule","checks":["finish_gte_start"]}','Schedule date logic is inconsistent.'),
('DQ-004','Progress outside 0..1','data_quality','critical','{"type":"range","fields":["planned_progress","actual_progress"],"min":0,"max":1}','Progress value is outside the canonical 0-100% range.'),
('CST-001','Actual cumulative cost > approved budget','cost','critical','{"type":"aggregate_compare","left":"actual_cost_cumulative","operator":">","right":"approved_budget"}','Cumulative actual cost has exceeded approved budget.'),
('CST-002','Actual cost > WBS budget','cost','warning','{"type":"aggregate_compare","group_by":["wbs_code"],"left":"actual_cost","operator":">","right":"budget"}','WBS actual cost exceeds its allocated budget.'),
('CST-003','Cost acceleration spike','cost','warning','{"type":"rolling_spike","metric":"monthly_cost","window":3,"threshold":1.5}','Recent spending is materially above the rolling baseline.'),
('CST-004','Actual + commitment > budget','cost','critical','{"type":"aggregate_compare","left":"actual_plus_commitment","operator":">","right":"approved_budget"}','Committed plus actual exposure is above approved budget.'),
('SCH-001','Activity past baseline finish and incomplete','schedule','warning','{"type":"date_status","condition":"today_gt_baseline_finish_and_not_complete"}','Activity has passed baseline finish without completion.'),
('SCH-002','Critical activity delayed','schedule','critical','{"type":"critical_delay","critical_flag":true,"status":"delayed"}','A critical-path activity is delayed.'),
('SCH-003','Actual progress behind planned','schedule','warning','{"type":"progress_gap","threshold":0.10}','Actual progress trails planned progress by more than the configured threshold.'),
('SCH-004','Negative float below threshold','schedule','critical','{"type":"float","threshold":-5}','Total float is materially negative.'),
('PRG-001','Progress behind plan','progress','warning','{"type":"progress_gap","threshold":0.10}','Actual progress is materially below planned progress.'),
('XDM-001','Cost rising while progress remains flat','cross_domain','critical','{"type":"cross_domain","cost_change":0.15,"progress_change":0.02}','Cost is increasing materially while progress remains nearly flat.')
ON CONFLICT (code) DO NOTHING;

COMMIT;
