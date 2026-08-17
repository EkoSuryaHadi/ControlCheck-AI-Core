from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ..models import EvidenceItem
from .base import BaseRule, row_evidence
from .schedule import _overdue


class ScheduleDelayHighCostExposureRule(BaseRule):
    rule_id = "XDOM-001"

    def evaluate(self, dataset, context):
        budgets, actuals, outstanding = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
        for item in dataset.budgets:
            if item.wbs_code:
                budgets[item.wbs_code] += item.budget_amount
        for item in dataset.actual_costs:
            if item.wbs_code:
                actuals[item.wbs_code] += item.actual_amount
        for item in dataset.commitments:
            if item.wbs_code and item.status.lower() == "open":
                outstanding[item.wbs_code] += max(item.committed_amount - item.invoiced_amount, Decimal("0"))
        delayed = defaultdict(list)
        for item in dataset.schedule:
            if item.wbs_code and (_overdue(item, dataset.data_date) or (item.critical and item.total_float_days < 0)):
                delayed[item.wbs_code].append(item)
        findings = []
        for wbs, activities in delayed.items():
            budget = budgets[wbs]
            if budget <= 0:
                continue
            exposure = actuals[wbs] + outstanding[wbs]
            ratio = exposure / budget
            if ratio < Decimal(str(context.thresholds.cross_domain_exposure_pct)) and actuals[wbs] / budget <= Decimal("0.90"):
                continue
            evidence = EvidenceItem(source_sheet="Schedule", source_rows=[x.source.row_number for x in activities],
                                    record_ids=[x.activity_id for x in activities], fields={"wbs_code": wbs, "delayed_count": len(activities)})
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=wbs,
                description=f"WBS {wbs} combines schedule delay with high cost exposure.",
                metrics={"budget": budget, "actual": actuals[wbs], "outstanding_commitment": outstanding[wbs], "exposure": exposure, "exposure_ratio": ratio},
                evidence=[evidence],
                calculation={"formula": "schedule_delay AND exposure_ratio >= 0.80", "value": ratio, "result": True},
            ))
        return findings


CROSS_DOMAIN_RULES = (ScheduleDelayHighCostExposureRule(),)

