import hashlib
import json


def test_reference_artifact_hashes(project_root):
    manifest_path = project_root / "docs" / "reference_artifacts_v0.1.sha256.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for name, expected in manifest.items():
        actual = hashlib.sha256((project_root / "docs" / name).read_bytes()).hexdigest().upper()
        assert actual == expected


def test_text_reference_artifacts_are_not_normalized_by_git(project_root):
    attributes = (project_root / ".gitattributes").read_text(encoding="utf-8")
    protected = {
        "docs/001_controlcheck_core_schema.sql",
        "docs/controlcheck_expected_findings_v0.1.json",
        "docs/controlcheck_rule_catalogue_v0.1.json",
    }

    for path in protected:
        assert f"{path} -text" in attributes
