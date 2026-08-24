-- Readable Phase 4B schema reference. Alembic is the executable authority.
-- Apply with: alembic upgrade head

-- Snapshot-scoped raw lineage and canonical facts are additive to 002.
-- The executable definitions live in alembic/versions/20260818_0002_*.py.
-- BIGINT raw-row IDs are intentionally used for long-lived source lineage.

-- Reference entities:
-- dataset_snapshots, dataset_domain_statuses, raw_rows,
-- wbs_facts, budget_facts, actual_cost_facts, commitment_facts,
-- schedule_facts, progress_facts.

-- Source anomalies are stored unchanged. DQ-003 and PRG-002 detect them;
-- ingestion never silently normalizes contradictory dates or >100% progress.
