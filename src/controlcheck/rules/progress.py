from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ..builders import severity_from_runtime
from .base import BaseRule, row_evidence, runtime_materiality, runtime_threshold


def _latest(dataset):
    result = {}
    for item in sorted(dataset.progress, key=lambda row: row.period):
        if item.wbs_code:
            result[item.wbs_code] = item
    return result


class WBSProgressLagRule(BaseRule):
    rule_id = "PRG-001"

    def evaluate(self, dataset, context):
        findings = []
        lag_min = float(runtime_threshold(
            context, self.rule_id, "lag_pp_min", context.thresholds.progress_lag_pp,
        ))
        critical_min = float(runtime_threshold(
            context, self.rule_id, "critical_lag_pp_min", context.thresholds.critical_progress_lag_pp,
        ))
        for wbs, item in _latest(dataset).items():
            lag = item.planned_progress - item.actual_progress
            if lag < lag_min:
                continue
            definition = context.definition(self.rule_id)
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=wbs,
                severity=severity_from_runtime(
                    definition, lag,
                    "critical" if lag >= critical_min else "warning",
                ),
                description=f"WBS {wbs} is {lag:.1%} behind planned progress.",
                metrics={"period": item.period, "planned_progress": item.planned_progress, "actual_progress": item.actual_progress, "lag_pp": lag},
                evidence=[row_evidence("Progress", item.progress_id, item.source,
                                       {"planned_progress": item.planned_progress, "actual_progress": item.actual_progress})],
                calculation={"formula": "planned_progress - actual_progress >= threshold", "value": lag, "threshold": lag_min, "result": True},
            ))
        return findings


class ProgressAbove100Rule(BaseRule):
    rule_id = "PRG-002"

    def evaluate(self, dataset, context):
        findings = []
        progress_max = float(runtime_threshold(context, self.rule_id, "progress_max", 1))
        for item in dataset.progress:
            if item.actual_progress <= progress_max and item.planned_progress <= progress_max:
                continue
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=item.wbs_code or item.progress_id,
                severity="critical", description=f"Progress for {item.wbs_code or item.progress_id} exceeds 100 percent.",
                metrics={"planned_progress": item.planned_progress, "actual_progress": item.actual_progress},
                evidence=[row_evidence("Progress", item.progress_id, item.source,
                                       {"planned_progress": item.planned_progress, "actual_progress": item.actual_progress})],
                calculation={"formula": "planned_progress > 1 OR actual_progress > 1", "result": True},
            ))
        return findings


class CostRisingProgressFlatRule(BaseRule):
    rule_id = "PRG-003"

    def evaluate(self, dataset, context):
        progress_by_wbs = defaultdict(list)
        for item in dataset.progress:
            if item.wbs_code:
                progress_by_wbs[item.wbs_code].append(item)
        cost_by_wbs_month = defaultdict(lambda: defaultdict(Decimal))
        for item in dataset.actual_costs:
            if item.wbs_code:
                cost_by_wbs_month[item.wbs_code][item.transaction_date.strftime("%Y-%m")] += item.actual_amount
        findings = []
        cost_change_min = Decimal(str(runtime_threshold(
            context, self.rule_id, "cost_change_pct_min", context.thresholds.rising_cost_change_pct,
        )))
        progress_change_max = float(runtime_threshold(
            context, self.rule_id, "progress_change_pp_max", context.thresholds.flat_progress_change_pp,
        ))
        project_budget = sum((item.budget_amount for item in dataset.budgets), Decimal("0"))
        current_materiality = project_budget * Decimal(str(runtime_materiality(
            context, self.rule_id, "current_period_project_budget_min", 0,
        )))
        for wbs, history in progress_by_wbs.items():
            history = sorted(history, key=lambda row: row.period)
            if len(history) < 2:
                continue
            previous, current = history[-2:]
            progress_change = current.actual_progress - previous.actual_progress
            current_month = current.period.strftime("%Y-%m")
            previous_month = previous.period.strftime("%Y-%m")
            current_cost = cost_by_wbs_month[wbs][current_month]
            previous_cost = cost_by_wbs_month[wbs][previous_month]
            if previous_cost > 0:
                cost_change = (current_cost - previous_cost) / previous_cost
            elif current_cost > 0:
                cost_change = Decimal("Infinity")
            else:
                cost_change = Decimal("0")
            if (cost_change < cost_change_min
                    or progress_change > progress_change_max + 1e-9
                    or current_cost < current_materiality):
                continue
            transactions = [x for x in dataset.actual_costs if x.wbs_code == wbs and x.transaction_date.strftime("%Y-%m") == current_month]
            from ..models import EvidenceItem
            cost_evidence = EvidenceItem(source_sheet="Actual_Cost", source_rows=[x.source.row_number for x in transactions],
                                         record_ids=[x.transaction_id for x in transactions], fields={"wbs_code": wbs, "period": current_month})
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=wbs,
                description=f"WBS {wbs} cost rose while physical progress remained nearly flat.",
                metrics={"previous_cost": previous_cost, "current_cost": current_cost, "cost_change_pct": cost_change,
                         "previous_progress": previous.actual_progress, "current_progress": current.actual_progress,
                         "progress_change_pp": progress_change},
                evidence=[cost_evidence,
                          row_evidence("Progress", previous.progress_id, previous.source, {"actual_progress": previous.actual_progress}),
                          row_evidence("Progress", current.progress_id, current.source, {"actual_progress": current.actual_progress})],
                calculation={"formula": "cost_change >= 20% AND progress_change <= 2pp", "result": True},
            ))
        return findings


PROGRESS_RULES = (WBSProgressLagRule(), ProgressAbove100Rule(), CostRisingProgressFlatRule())
