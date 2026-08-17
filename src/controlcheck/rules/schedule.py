from __future__ import annotations

from ..builders import severity_from_runtime
from .base import BaseRule, row_evidence, runtime_threshold


def _completed(activity) -> bool:
    return activity.status.strip().lower() in {"complete", "completed", "cancelled", "canceled"}


def _overdue(activity, data_date) -> bool:
    return not _completed(activity) and activity.actual_progress < 1 and activity.baseline_finish < data_date


class OverdueActivityRule(BaseRule):
    rule_id = "SCH-001"

    def evaluate(self, dataset, context):
        findings = []
        overdue_min = int(runtime_threshold(context, self.rule_id, "overdue_days_min", 1))
        critical_min = int(runtime_threshold(context, self.rule_id, "critical_days_min", 14))
        for item in dataset.schedule:
            if not _overdue(item, dataset.data_date):
                continue
            days = (dataset.data_date - item.baseline_finish).days
            if days < overdue_min:
                continue
            definition = context.definition(self.rule_id)
            severity = (
                "critical" if item.critical
                else severity_from_runtime(
                    definition, days,
                    "critical" if days >= critical_min else "warning",
                )
            )
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
        slippage_min = int(runtime_threshold(
            context, self.rule_id, "slippage_days_min", context.thresholds.schedule_slippage_days,
        ))
        critical_min = int(runtime_threshold(context, self.rule_id, "critical_days_min", 14))
        for item in dataset.schedule:
            if item.actual_finish is None:
                continue
            days = (item.actual_finish - item.baseline_finish).days
            if days < slippage_min:
                continue
            definition = context.definition(self.rule_id)
            findings.append(self.finding(
                dataset, context, entity_type="activity", entity_id=item.activity_id,
                severity=severity_from_runtime(
                    definition, days,
                    "critical" if days >= critical_min else "warning",
                ),
                description=f"Activity {item.activity_id} finished {days} days after baseline.",
                metrics={"slippage_days": days},
                evidence=[row_evidence("Schedule", item.activity_id, item.source,
                                       {"baseline_finish": item.baseline_finish, "actual_finish": item.actual_finish})],
                calculation={"formula": "actual_finish - baseline_finish >= threshold", "value": days, "threshold": slippage_min, "result": True},
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
        lag_min = float(runtime_threshold(
            context, self.rule_id, "lag_pp_min", context.thresholds.progress_lag_pp,
        ))
        critical_min = float(runtime_threshold(
            context, self.rule_id, "critical_lag_pp_min", context.thresholds.critical_progress_lag_pp,
        ))
        for item in dataset.schedule:
            lag = item.planned_progress - item.actual_progress
            if lag < lag_min:
                continue
            definition = context.definition(self.rule_id)
            severity = (
                severity_from_runtime(definition, lag, "critical")
                if item.critical and lag >= critical_min else "warning"
            )
            findings.append(self.finding(
                dataset, context, entity_type="activity", entity_id=item.activity_id,
                severity=severity, description=f"Activity {item.activity_id} is {lag:.1%} behind planned progress.",
                metrics={"planned_progress": item.planned_progress, "actual_progress": item.actual_progress, "lag_pp": lag},
                evidence=[row_evidence("Schedule", item.activity_id, item.source,
                                       {"planned_progress": item.planned_progress, "actual_progress": item.actual_progress})],
                calculation={"formula": "planned_progress - actual_progress >= threshold", "value": lag, "threshold": lag_min, "result": True},
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
