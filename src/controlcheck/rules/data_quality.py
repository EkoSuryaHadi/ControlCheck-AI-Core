from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from ..models import EvidenceItem, ProjectDataset
from .base import BaseRule, row_evidence


def _norm_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _domain_records(dataset: ProjectDataset):
    yield "Budget", dataset.budgets, "budget_id"
    yield "Actual_Cost", dataset.actual_costs, "transaction_id"
    yield "Commitments", dataset.commitments, "commitment_id"
    yield "Schedule", dataset.schedule, "activity_id"
    yield "Progress", dataset.progress, "progress_id"


class MissingWBSRule(BaseRule):
    rule_id = "DQ-001"

    def evaluate(self, dataset, context):
        findings = []
        for sheet, records, id_field in _domain_records(dataset):
            for record in records:
                if record.wbs_code is None:
                    record_id = getattr(record, id_field)
                    evidence = row_evidence(sheet, record_id, record.source, {"wbs_code": None})
                    findings.append(self.finding(
                        dataset, context, entity_type="record", entity_id=record_id,
                        severity="critical", description=f"{sheet} record {record_id} has no WBS reference.",
                        metrics={"missing_wbs_count": 1}, evidence=[evidence],
                        calculation={"field": "wbs_code", "operator": "is_null", "result": True},
                    ))
        return findings


class DuplicateCostRule(BaseRule):
    rule_id = "DQ-002"

    def evaluate(self, dataset, context):
        groups = defaultdict(list)
        for record in dataset.actual_costs:
            key = (
                record.transaction_date.isoformat(), record.wbs_code,
                record.vendor_id or _norm_text(record.vendor_name), record.po_number,
                str(record.actual_amount), _norm_text(record.description),
            )
            groups[key].append(record)
        findings = []
        for key, records in groups.items():
            if len(records) < 2:
                continue
            ids = sorted(record.transaction_id for record in records)
            evidence = EvidenceItem(
                source_sheet="Actual_Cost", source_rows=[r.source.row_number for r in records],
                record_ids=ids, fields={"duplicate_key": list(key), "count": len(records)},
            )
            findings.append(self.finding(
                dataset, context, entity_type="transaction_group", entity_id="/".join(ids),
                description=f"{len(records)} probable duplicate cost transactions share the same normalized key.",
                metrics={"duplicate_count": len(records), "amount": records[0].actual_amount},
                evidence=[evidence], calculation={"operator": "group_count_gte", "threshold": 2, "result": len(records)},
            ))
        return findings


class ContradictoryDateProgressRule(BaseRule):
    rule_id = "DQ-003"

    def evaluate(self, dataset, context):
        findings = []
        for activity in dataset.schedule:
            finish_before_start = bool(activity.actual_start and activity.actual_finish and activity.actual_finish < activity.actual_start)
            invalid_progress = activity.actual_progress < 0 or activity.actual_progress > 1 or activity.planned_progress < 0 or activity.planned_progress > 1
            if finish_before_start or invalid_progress:
                fields = {"actual_start": activity.actual_start, "actual_finish": activity.actual_finish,
                          "planned_progress": activity.planned_progress, "actual_progress": activity.actual_progress}
                findings.append(self.finding(
                    dataset, context, entity_type="activity", entity_id=activity.activity_id,
                    severity="critical", description=f"Activity {activity.activity_id} contains contradictory dates or progress.",
                    metrics={"finish_before_start": finish_before_start, "invalid_progress": invalid_progress},
                    evidence=[row_evidence("Schedule", activity.activity_id, activity.source, fields)],
                    calculation={"operator": "or", "conditions": fields, "result": True},
                ))
        return findings


class OrphanWBSRule(BaseRule):
    rule_id = "DQ-004"

    def evaluate(self, dataset, context):
        known = {node.wbs_code for node in dataset.wbs_nodes}
        findings = []
        for sheet, records, id_field in _domain_records(dataset):
            for record in records:
                if record.wbs_code is not None and record.wbs_code not in known:
                    record_id = getattr(record, id_field)
                    findings.append(self.finding(
                        dataset, context, entity_type="record", entity_id=record_id,
                        severity="critical", description=f"{sheet} record {record_id} references unknown WBS {record.wbs_code}.",
                        metrics={"wbs_code": record.wbs_code},
                        evidence=[row_evidence(sheet, record_id, record.source, {"wbs_code": record.wbs_code})],
                        calculation={"operator": "not_in_wbs_master", "value": record.wbs_code, "result": True},
                    ))
        return findings


class VendorIdentityRule(BaseRule):
    rule_id = "DQ-005"

    def evaluate(self, dataset, context):
        by_vendor = defaultdict(list)
        for record in dataset.actual_costs:
            if record.vendor_id and record.vendor_name:
                by_vendor[record.vendor_id].append(record)
        findings = []
        for vendor_id, records in by_vendor.items():
            names = Counter(_norm_text(record.vendor_name) for record in records)
            if len(names) <= 1:
                continue
            canonical = names.most_common(1)[0][0]
            for record in records:
                if _norm_text(record.vendor_name) == canonical:
                    continue
                findings.append(self.finding(
                    dataset, context, entity_type="transaction", entity_id=record.transaction_id,
                    description=f"Vendor {vendor_id} uses inconsistent name {record.vendor_name!r}.",
                    metrics={"vendor_id": vendor_id, "variant_count": len(names)},
                    evidence=[row_evidence("Actual_Cost", record.transaction_id, record.source,
                                           {"vendor_id": vendor_id, "vendor_name": record.vendor_name,
                                            "canonical_normalized_name": canonical})],
                    calculation={"operator": "normalized_name_not_equal", "result": True},
                ))
        return findings


DATA_QUALITY_RULES = (
    MissingWBSRule(), DuplicateCostRule(), ContradictoryDateProgressRule(),
    OrphanWBSRule(), VendorIdentityRule(),
)
