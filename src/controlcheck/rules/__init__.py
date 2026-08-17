"""Deterministic rule implementations."""

from .cost import COST_RULES
from .cross_domain import CROSS_DOMAIN_RULES
from .data_quality import DATA_QUALITY_RULES
from .progress import PROGRESS_RULES
from .schedule import SCHEDULE_RULES


ALL_RULES = tuple(sorted(
    DATA_QUALITY_RULES + COST_RULES + SCHEDULE_RULES + PROGRESS_RULES + CROSS_DOMAIN_RULES,
    key=lambda rule: rule.rule_id,
))
