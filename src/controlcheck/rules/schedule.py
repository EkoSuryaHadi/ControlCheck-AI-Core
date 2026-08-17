from __future__ import annotations

from .base import BaseRule, row_evidence


def _completed(activity) -> bool:
    return activity.status.strip().lower() in {"complete", "completed", "cancelled", "canceled"}


def _overdue(activity, data_date) -> bool:
    return not _completed(activity) and activity.actual_progress < 1 and activity.baseline_finish < data_date


class OverdueActivityRule(BaseRule):
    rule_id = "SCH-001"

    def evaluate(self, dataset, context):
        findings = []
        for item in dataset.schedule:
            if not _overdue(item, dataset.data_date):
                continue
            days = (dataset.data_date - item.baseline_finish).days
            severity = "critical" if item.critical or days >= 14 else "warning"
            fields = {"baseline_finish": item.baseline_finish, "actual_progress": item.actual_progress,
                      "status": item.status, "critical": item.critical}
            findings.append(self.finding(
                dataset, context, entity_type="activity", entity_id=item.activity_id,
                severity=severity, description=f"Activity {item.activity_id} is overdue by {days} days.",
                metrics={"overdue_days": days, "actual_progress": item.actual_progress},
                evidence=[row_evidence("Schedule", item.activity_id, item.source, fields)],
                calculation={"formula": "incomplete AND baseline_finish < data_date", "data_date": dataset.data_date, "result": True},
            ))
        return findings


class BaselineFinishSlippageRule(BaseRule):
    rule_id = "SCH-002"

    def evaluate(self, dataset, context):
        findings = []
        for item in dataset.schedule:
            if item.actual_finish is None:
                continue
            days = (item.actual_finish - item.baseline_finish).days
            if days < context.thresholds.schedule_slippage_days:
                continue
            findings.append(self.finding(
                dataset, context, entity_type="activity", entity_id=item.activity_id,
                severity="critical" if days >= 14 else "warning",
                description=f"Activity {item.activity_id} finished {days} days after baseline.",
                metrics={"slippage_days": days},
                evidence=[row_evidence("Schedule", item.activity_id, item.source,
                                       {"baseline_finish": item.baseline_finish, "actual_finish": item.actual_finish})],
                calculation={"formula": "actual_finish - baseline_finish >= threshold", "value": days, "threshold": context.thresholds.schedule_slippage_days, "result": True},
            ))
        return findings


class CriticalActivityDelayRule(BaseRule):
    rule_id = "SCH-003"

    def evaluate(self, dataset, context):
        findings = []
        for item in dataset.schedule:
            late_finish = bool(item.actual_finish and item.actual_finish > item.baseline_finish)
            delay = _overdue(item, dataset.data_date) or late_finish or item.total_float_days < 0
            if not item.critical or not delay:
                continue
            findings.append(self.finding(
                dataset, context, entity_type="activity", entity_id=item.activity_id,
                description=f"Critical activity {item.activity_id} is delayed or at risk.",
                metrics={"overdue": _overdue(item, dataset.data_date), "late_finish": late_finish, "total_float_days": item.total_float_days},
                evidence=[row_evidence("Schedule", item.activity_id, item.source,
                                       {"critical": item.critical, "baseline_finish": item.baseline_finish,
                                        "actual_finish": item.actual_finish, "total_float_days": item.total_float_days})],
                calculation={"formula": "critical AND (overdue OR late_finish OR negative_float)", "result": True},
            ))
        return findings


class ActivityProgressLagRule(BaseRule):
    rule_id = "SCH-004"

    def evaluate(self, dataset, context):
        findings = []
        for item in dataset.schedule:
            lag = item.planned_progress - item.actual_progress
            if lag < context.thresholds.progress_lag_pp:
                continue
            severity = "critical" if item.critical and lag >= context.thresholds.critical_progress_lag_pp else "warning"
            findings.append(self.finding(
                dataset, context, entity_type="activity", entity_id=item.activity_id,
                severity=severity, description=f"Activity {item.activity_id} is {lag:.1%} behind planned progress.",
                metrics={"planned_progress": item.planned_progress, "actual_progress": item.actual_progress, "lag_pp": lag},
                evidence=[row_evidence("Schedule", item.activity_id, item.source,
                                       {"planned_progress": item.planned_progress, "actual_progress": item.actual_progress})],
                calculation={"formula": "planned_progress - actual_progress >= threshold", "value": lag, "threshold": context.thresholds.progress_lag_pp, "result": True},
            ))
        return findings


class NegativeFloatRule(BaseRule):
    rule_id = "SCH-005"

    def evaluate(self, dataset, context):
        findings = []
        for item in dataset.schedule:
            if item.total_float_days >= 0:
                continue
            findings.append(self.finding(
                dataset, context, entity_type="activity", entity_id=item.activity_id,
                description=f"Activity {item.activity_id} has {item.total_float_days} days total float.",
                metrics={"total_float_days": item.total_float_days},
                evidence=[row_evidence("Schedule", item.activity_id, item.source, {"total_float_days": item.total_float_days})],
                calculation={"formula": "total_float_days < 0", "value": item.total_float_days, "result": True},
            ))
        return findings


SCHEDULE_RULES = (
    OverdueActivityRule(), BaselineFinishSlippageRule(), CriticalActivityDelayRule(),
    ActivityProgressLagRule(), NegativeFloatRule(),
)

