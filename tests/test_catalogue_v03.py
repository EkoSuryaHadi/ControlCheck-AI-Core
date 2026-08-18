from controlcheck.config import load_catalogue


def test_catalogue_v03_has_explicit_dependencies_for_all_rules(project_root):
    catalogue = load_catalogue(project_root / "data/controlcheck_rule_catalogue_v0.3.json")

    assert len(catalogue.rules) == 20
    assert all(rule.runtime.required_domains for rule in catalogue.rules)
    assert catalogue.by_id("CST-006").runtime.required_domains == [
        "wbs",
        "budget",
        "actual_cost",
        "progress",
    ]
