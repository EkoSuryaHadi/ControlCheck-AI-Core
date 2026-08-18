from controlcheck.ingestion.profile import load_mapping_profile


def test_governed_profile_declares_exact_domains_and_columns(project_root):
    profile = load_mapping_profile(
        project_root / "data/controlcheck_mapping_profile_v0.1.json"
    )

    assert profile.version == "0.1"
    assert set(profile.domains) == {
        "wbs",
        "budget",
        "actual_cost",
        "commitments",
        "schedule",
        "progress",
    }
    assert profile.domains["actual_cost"].sheet_name == "Actual_Cost"
    assert profile.domains["actual_cost"].columns["transaction_id"].required is True
