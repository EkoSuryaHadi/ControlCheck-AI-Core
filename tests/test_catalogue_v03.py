import copy
import json

from controlcheck.config import load_catalogue


REQUIRED_DOMAINS_BY_RULE = {
    "DQ-001": ["wbs", "budget", "actual_cost", "schedule", "progress"],
    "DQ-002": ["actual_cost"],
    "DQ-003": ["schedule", "progress"],
    "DQ-004": ["wbs", "budget", "actual_cost", "commitments", "schedule", "progress"],
    "DQ-005": ["actual_cost"],
    "CST-001": ["wbs", "budget", "actual_cost"],
    "CST-002": ["wbs", "budget", "actual_cost", "commitments"],
    "CST-003": ["wbs", "budget", "actual_cost"],
    "CST-004": ["actual_cost"],
    "CST-005": ["wbs", "budget", "actual_cost"],
    "CST-006": ["wbs", "budget", "actual_cost", "progress"],
    "SCH-001": ["schedule"],
    "SCH-002": ["schedule"],
    "SCH-003": ["schedule"],
    "SCH-004": ["schedule"],
    "SCH-005": ["schedule"],
    "PRG-001": ["wbs", "progress"],
    "PRG-002": ["progress", "schedule"],
    "PRG-003": ["wbs", "budget", "actual_cost", "progress"],
    "XDOM-001": ["wbs", "budget", "actual_cost", "commitments", "schedule", "progress"],
}


def test_catalogue_v03_has_the_complete_exact_rule_dependency_map(project_root):
    catalogue = load_catalogue(project_root / "data/controlcheck_rule_catalogue_v0.3.json")

    assert len(catalogue.rules) == 20
    assert {
        rule.code: rule.runtime.required_domains for rule in catalogue.rules
    } == REQUIRED_DOMAINS_BY_RULE


def test_catalogue_v03_is_v02_plus_version_and_rule_dependencies(project_root):
    v02 = json.loads(
        (project_root / "data/controlcheck_rule_catalogue_v0.2.json").read_text(
            encoding="utf-8"
        )
    )
    v03 = json.loads(
        (project_root / "data/controlcheck_rule_catalogue_v0.3.json").read_text(
            encoding="utf-8"
        )
    )
    restored = copy.deepcopy(v03)
    restored["version"] = "0.2"
    for rule in restored["rules"]:
        rule["runtime"].pop("required_domains")

    assert restored == v02
