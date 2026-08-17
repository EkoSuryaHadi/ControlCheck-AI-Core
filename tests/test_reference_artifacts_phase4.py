import hashlib
import json


def test_reference_artifact_hashes(project_root):
    manifest_path = project_root / "docs" / "reference_artifacts_v0.1.sha256.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for name, expected in manifest.items():
        actual = hashlib.sha256((project_root / "docs" / name).read_bytes()).hexdigest().upper()
        assert actual == expected
