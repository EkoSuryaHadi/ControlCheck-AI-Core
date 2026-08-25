import hashlib
from pathlib import Path
from uuid import UUID

from controlcheck.storage import LocalFileStorage
from controlcheck.storage_s3 import S3FileStorage


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


class _MissingObjectError(Exception):
    response = {"ResponseMetadata": {"HTTPStatusCode": 404}}


class _FakeS3Client:
    def __init__(self, *, missing: bool = False, ready: bool = True):
        self.missing = missing
        self.ready = ready
        self.head_object_calls: list[dict[str, str]] = []
        self.head_bucket_calls: list[dict[str, str]] = []

    def head_object(self, **kwargs):
        self.head_object_calls.append(kwargs)
        if self.missing:
            raise _MissingObjectError()
        return {"ContentLength": 4}

    def head_bucket(self, **kwargs):
        self.head_bucket_calls.append(kwargs)
        if not self.ready:
            raise RuntimeError("unsafe provider detail")
        return {}


def test_s3_storage_exists_uses_head_object_contract():
    client = _FakeS3Client()
    storage = S3FileStorage(bucket="workbooks")
    storage._client = client

    assert storage.exists("org/project/workbook.xlsx") is True
    assert client.head_object_calls == [
        {"Bucket": "workbooks", "Key": "org/project/workbook.xlsx"}
    ]


def test_s3_storage_exists_returns_false_for_missing_object():
    storage = S3FileStorage(bucket="workbooks")
    storage._client = _FakeS3Client(missing=True)

    assert storage.exists("missing.xlsx") is False


def test_s3_storage_readiness_checks_bucket_access():
    client = _FakeS3Client()
    storage = S3FileStorage(bucket="workbooks")
    storage._client = client

    assert storage.is_ready() is True
    assert client.head_bucket_calls == [{"Bucket": "workbooks"}]
