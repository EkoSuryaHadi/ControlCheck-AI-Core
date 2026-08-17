import hashlib
from pathlib import Path
from uuid import UUID

from controlcheck.storage import LocalFileStorage


ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_storage_writes_under_configured_root(tmp_path):
    stored = LocalFileStorage(tmp_path).put(ORG_ID, PROJECT_ID, "project.xlsx", b"xlsx")

    assert (tmp_path / stored.key).read_bytes() == b"xlsx"
    assert stored.sha256 == hashlib.sha256(b"xlsx").hexdigest()
    assert stored.size_bytes == 4


def test_storage_discards_path_traversal(tmp_path):
    stored = LocalFileStorage(tmp_path).put(ORG_ID, PROJECT_ID, "../../outside.xlsx", b"xlsx")

    assert Path(stored.key).name == "outside.xlsx"
    assert not (tmp_path.parent / "outside.xlsx").exists()


def test_storage_delete_is_idempotent(tmp_path):
    storage = LocalFileStorage(tmp_path)
    stored = storage.put(ORG_ID, PROJECT_ID, "project.xlsx", b"xlsx")

    storage.delete(stored.key)
    storage.delete(stored.key)

    assert not (tmp_path / stored.key).exists()
