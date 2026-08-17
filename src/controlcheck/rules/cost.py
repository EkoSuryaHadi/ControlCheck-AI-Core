from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ..builders import severity_from_runtime
from ..models import EvidenceItem
from .base import BaseRule, row_evidence, runtime_threshold


def _sum_by(records, key_name: str, value_name: str):
    totals = defaultdict(Decimal)
    for record in records:
        key = getattr(record, key_name)
        if key is not None:
            totals[key] += getattr(record, value_name)
    return totals


def _budgets(dataset):
    return _sum_by(dataset.budgets, "wbs_code", "budget_amount")


def _actuals(dataset):
    return _sum_by(dataset.actual_costs, "wbs_code", "actual_amount")


def _latest_progress(dataset):
    latest = {}
    for record in sorted(dataset.progress, key=lambda item: item.period):
        if record.wbs_code is not None:
            latest[record.wbs_code] = record
    return latest


def _aggregate_evidence(sheet, records, fields):
    return EvidenceItem(
        source_sheet=sheet,
        source_rows=[record.source.row_number for record in records],
        record_ids=[getattr(record, "transaction_id", getattr(record, "commitment_id", getattr(record, "budget_id", ""))) for record in records],
        fields=fields,
        aggregation={"record_count": len(records)},
    )


class ActualExceedsBudgetRule(BaseRule):
    rule_id = "CST-001"

    def evaluate(self, dataset, context):
        budgets, actuals = _budgets(dataset), _actuals(dataset)
        findings = []
        ratio_min = Decimal(str(runtime_threshold(context, self.rule_id, "actual_budget_ratio_min", 1)))
        for wbs, budget in budgets.items():
            actual = actuals[wbs]
            ratio = actual / budget if budget else Decimal("0")
            if ratio <= ratio_min:
                continue
            variance = actual - budget
            transactions = [x for x in dataset.actual_costs if x.wbs_code == wbs]
            definition = context.definition(self.rule_id)
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=wbs,
                severity=severity_from_runtime(
                    definition, ratio,
                    "critical" if ratio >= Decimal("1.10") else "warning",
                ),
                description=f"WBS {wbs} actual cost exceeds budget by {variance}.",
                metrics={"budget": budget, "actual": actual, "variance": variance, "actual_budget_ratio": ratio},
                evidence=[_aggregate_evidence("Actual_Cost", transactions, {"wbs_code": wbs, "actual": actual, "budget": budget})],
                calculation={"formula": "actual > budget", "left": actual, "right": budget, "result": True},
            ))
        return findings


class ExposureExceedsBudgetRule(BaseRule):
    rule_id = "CST-002"

    def evaluate(self, dataset, context):
        budgets, actuals = _budgets(dataset), _actuals(dataset)
        outstanding = defaultdict(Decimal)
        for item in dataset.commitments:
            if item.wbs_code and item.status.lower() == "open":
                outstanding[item.wbs_code] += max(item.committed_amount - item.invoiced_amount, Decimal("0"))
        findings = []
        ratio_min = Decimal(str(runtime_threshold(context, self.rule_id, "exposure_budget_ratio_min", 1)))
        for wbs, budget in budgets.items():
            exposure = actuals[wbs] + outstanding[wbs]
            ratio = exposure / budget if budget else Decimal("0")
            if ratio <= ratio_min:
                continue
            records = [x for x in dataset.commitments if x.wbs_code == wbs and x.status.lower() == "open"]
            definition = context.definition(self.rule_id)
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=wbs,
                severity=severity_from_runtime(
                    definition, ratio,
                    "critical" if ratio >= Decimal("1.10") else "warning",
                ),
                description=f"WBS {wbs} actual plus outstanding commitment exceeds budget.",
                metrics={"budget": budget, "actual": actuals[wbs], "outstanding_commitment": outstanding[wbs], "exposure": exposure, "exposure_ratio": ratio},
                evidence=[_aggregate_evidence("Commitments", records, {"wbs_code": wbs, "exposure": exposure, "budget": budget})],
                calculation={"formula": "actual + max(committed - invoiced, 0) > budget", "left": exposure, "right": budget, "result": True},
            ))
        return findings


class CostSpikeRule(BaseRule):
    rule_id = "CST-003"

    def evaluate(self, dataset, context):
        monthly = defaultdict(lambda: defaultdict(Decimal))
        for item in dataset.actual_costs:
            if item.wbs_code:
                monthly[item.wbs_code][item.transaction_date.strftime("%Y-%m")] += item.actual_amount
        project_budget = sum((x.budget_amount for x in dataset.budgets), Decimal("0"))
        findings = []
        for wbs, periods in monthly.items():
            ordered = sorted(periods)
            if len(ordered) < 2:
                continue
            current_period = ordered[-1]
            history = [periods[p] for p in ordered[-4:-1]]
            average = sum(history, Decimal("0")) / len(history)
            current = periods[current_period]
            multiplier = runtime_threshold(
                context, self.rule_id, "run_rate_multiplier_min",
                context.thresholds.cost_spike_multiplier,
            )
            project_share = runtime_threshold(
                context, self.rule_id, "project_budget_share_min",
                context.thresholds.cost_spike_materiality_bac,
            )
            threshold = average * Decimal(str(multiplier))
            materiality = project_budget * Decimal(str(project_share))
            if average <= 0 or current < threshold or current < materiality:
                continue
            records = [x for x in dataset.actual_costs if x.wbs_code == wbs and x.transaction_date.strftime("%Y-%m") == current_period]
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=wbs,
                description=f"WBS {wbs} current-period cost is materially above its recent run rate.",
                metrics={"current_period": current_period, "current_cost": current, "recent_average": average, "ratio": current / average},
                evidence=[_aggregate_evidence("Actual_Cost", records, {"wbs_code": wbs, "period": current_period})],
                calculation={"formula": "current >= recent_average * multiplier", "current": current, "threshold": threshold, "result": True},
            ))
        return findings


class VendorConcentrationRule(BaseRule):
    rule_id = "CST-004"

    def evaluate(self, dataset, context):
        wbs_total = _actuals(dataset)
        vendor_wbs = defaultdict(Decimal)
        for item in dataset.actual_costs:
            if item.wbs_code and item.vendor_id:
                vendor_wbs[(item.vendor_id, item.wbs_code)] += item.actual_amount
        definition = context.definition(self.rule_id)
        runtime = getattr(definition, "runtime", None)
        warning_threshold = Decimal(str(runtime_threshold(
            context, self.rule_id, "warning_share_min",
            context.thresholds.vendor_concentration_warning,
        )))
        critical_threshold = Decimal(str(runtime_threshold(
            context, self.rule_id, "critical_share_min",
            context.thresholds.vendor_concentration_critical,
        )))
        candidates = []
        if runtime is not None:
            for (vendor, wbs), amount in vendor_wbs.items():
                share = amount / wbs_total[wbs] if wbs_total[wbs] else Decimal("0")
                candidates.append((vendor, share, wbs, amount))
        else:
            strongest = {}
            for (vendor, wbs), amount in vendor_wbs.items():
                share = amount / wbs_total[wbs] if wbs_total[wbs] else Decimal("0")
                if vendor not in strongest or share > strongest[vendor][0]:
                    strongest[vendor] = (share, wbs, amount)
            candidates = [
                (vendor, share, wbs, amount)
                for vendor, (share, wbs, amount) in strongest.items()
            ]
        findings = []
        for vendor, share, wbs, amount in candidates:
            if share < warning_threshold:
                continue
            records = [x for x in dataset.actual_costs if x.wbs_code == wbs and x.vendor_id == vendor]
            entity_type = "vendor_wbs" if runtime is not None else "vendor"
            entity_id = f"{wbs}|{vendor}" if runtime is not None else vendor
            findings.append(self.finding(
                dataset, context, entity_type=entity_type, entity_id=entity_id,
                severity=severity_from_runtime(
                    definition, share,
                    "critical" if share >= critical_threshold else "warning",
                ),
                description=f"Vendor {vendor} represents {share:.1%} of WBS {wbs} actual cost.",
                metrics={"vendor": vendor, "wbs_code": wbs, "vendor_actual": amount, "wbs_actual": wbs_total[wbs], "share": share},
                evidence=[_aggregate_evidence("Actual_Cost", records, {"vendor_id": vendor, "wbs_code": wbs})],
                calculation={"formula": "vendor_wbs_actual / wbs_actual >= threshold", "value": share, "threshold": warning_threshold, "result": True},
            ))
        return findings


class HighValueTransactionRule(BaseRule):
    rule_id = "CST-005"

    def evaluate(self, dataset, context):
        budgets = _budgets(dataset)
        project_budget = sum(budgets.values(), Decimal("0"))
        definition = context.definition(self.rule_id)
        runtime = getattr(definition, "runtime", None)
        wbs_min = Decimal(str(runtime_threshold(
            context, self.rule_id, "wbs_share_min",
            context.thresholds.transaction_wbs_share,
        )))
        project_min = Decimal(str(runtime_threshold(
            context, self.rule_id, "project_share_min",
            context.thresholds.transaction_project_share,
        )))
        findings = []
        for item in dataset.actual_costs:
            budget = budgets.get(item.wbs_code or "", Decimal("0"))
            wbs_share = item.actual_amount / budget if budget else Decimal("0")
            project_share = item.actual_amount / project_budget if project_budget else Decimal("0")
            if runtime is not None:
                triggered = wbs_share >= wbs_min and project_share >= project_min
            else:
                triggered = wbs_share >= wbs_min or project_share >= project_min
            if not triggered:
                continue
            findings.append(self.finding(
                dataset, context, entity_type="transaction", entity_id=item.transaction_id,
                severity=severity_from_runtime(
                    definition, wbs_share,
                    "critical" if wbs_share >= Decimal("0.25") else "observation",
                ),
                description=f"Transaction {item.transaction_id} is material relative to its budget context.",
                metrics={"amount": item.actual_amount, "wbs_budget": budget, "wbs_share": wbs_share, "project_share": project_share},
                evidence=[row_evidence("Actual_Cost", item.transaction_id, item.source, {"wbs_code": item.wbs_code, "vendor_id": item.vendor_id, "po_number": item.po_number, "amount": item.actual_amount})],
                calculation={
                    "formula": (
                        "wbs_share >= threshold AND project_share >= threshold"
                        if runtime is not None
                        else "wbs_share >= threshold OR project_share >= threshold"
                    ),
                    "wbs_threshold": wbs_min,
                    "project_threshold": project_min,
                    "result": True,
                },
            ))
        return findings


class HighCostLowProgressRule(BaseRule):
    rule_id = "CST-006"

    def evaluate(self, dataset, context):
        budgets, actuals, progress = _budgets(dataset), _actuals(dataset), _latest_progress(dataset)
        cost_min = Decimal(str(runtime_threshold(
            context, self.rule_id, "cost_pct_min", context.thresholds.cost_progress_cost_pct,
        )))
        progress_max = float(runtime_threshold(
            context, self.rule_id, "progress_pct_max", context.thresholds.cost_progress_max_progress,
        ))
        findings = []
        for wbs, latest in progress.items():
            budget = budgets.get(wbs, Decimal("0"))
            if budget <= 0:
                continue
            cost_pct = actuals[wbs] / budget
            if cost_pct < cost_min or latest.actual_progress > progress_max:
                continue
            transactions = [x for x in dataset.actual_costs if x.wbs_code == wbs]
            findings.append(self.finding(
                dataset, context, entity_type="wbs", entity_id=wbs,
                description=f"WBS {wbs} has high cost consumption with low physical progress.",
                metrics={"budget": budget, "actual": actuals[wbs], "cost_pct": cost_pct, "actual_progress": latest.actual_progress},
                evidence=[_aggregate_evidence("Actual_Cost", transactions, {"wbs_code": wbs}),
                          row_evidence("Progress", latest.progress_id, latest.source, {"actual_progress": latest.actual_progress, "period": latest.period})],
                calculation={"formula": "cost_pct >= 0.80 AND progress <= 0.50", "result": True},
            ))
        return findings


COST_RULES = (
    ActualExceedsBudgetRule(), ExposureExceedsBudgetRule(), CostSpikeRule(),
    VendorConcentrationRule(), HighValueTransactionRule(), HighCostLowProgressRule(),
)
