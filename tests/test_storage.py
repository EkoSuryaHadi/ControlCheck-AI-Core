import hashlib
from pathlib import Path
from uuid import UUID

import pytest
from botocore.exceptions import ClientError

import controlcheck.errors as application_errors
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


class _FailingS3Client:
    @staticmethod
    def _failure(operation: str):
        raise ClientError(
            {
                "Error": {"Code": "AccessDenied", "Message": "provider secret"},
                "ResponseMetadata": {"HTTPStatusCode": 403},
            },
            operation,
        )

    def put_object(self, **kwargs):
        self._failure("PutObject")

    def head_object(self, **kwargs):
        self._failure("HeadObject")


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


@pytest.mark.parametrize("operation", ["put", "head"])
def test_s3_provider_failures_use_storage_unavailable_error(operation):
    storage = S3FileStorage(bucket="workbooks")
    storage._client = _FailingS3Client()
    unavailable_error = application_errors.StorageUnavailableError

    with pytest.raises(unavailable_error) as caught:
        if operation == "put":
            storage.put(ORG_ID, PROJECT_ID, "project.xlsx", b"xlsx")
        else:
            storage.exists("org/project/project.xlsx")

    assert "provider secret" not in str(caught.value)
