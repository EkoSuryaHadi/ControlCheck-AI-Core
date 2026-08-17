from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    name: str
    category: str
    severity: str
    objective: str
    inputs: str
    logic: str
    threshold: str
    evidence: str
    finding: str
    impact: str
    recommendation: str
    false_positive: str
    acceptance: str


class RuleCatalogue(BaseModel):
    version: str
    rules: list[RuleDefinition]

    def by_id(self, rule_id: str) -> RuleDefinition:
        for rule in self.rules:
            if rule.code == rule_id:
                return rule
        raise KeyError(f"Unknown rule: {rule_id}")


class ThresholdConfig(BaseModel):
    cost_spike_multiplier: float = 1.30
    cost_spike_materiality_bac: float = 0.01
    vendor_concentration_warning: float = 0.40
    vendor_concentration_critical: float = 0.60
    transaction_wbs_share: float = 0.05
    transaction_project_share: float = 0.02
    progress_lag_pp: float = 0.10
    cost_progress_cost_pct: float = 0.80
    cost_progress_max_progress: float = 0.50
    schedule_slippage_days: int = 7
    critical_progress_lag_pp: float = 0.20
    rising_cost_change_pct: float = 0.20
    flat_progress_change_pp: float = 0.02
    cross_domain_exposure_pct: float = 0.80


def load_catalogue(path: Path | str) -> RuleCatalogue:
    return RuleCatalogue.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
