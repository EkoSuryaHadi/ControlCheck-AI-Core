from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from .storage import StoredObject
from .errors import StorageUnavailableError


class S3FileStorage:
    """Production S3 / MinIO compatible object storage backend."""

    def __init__(
        self,
        bucket: str,
        region: str = "ap-southeast-1",
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ):
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    region_name=self.region,
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                )
            except ImportError as exc:
                raise StorageUnavailableError() from exc
            except Exception as exc:
                raise StorageUnavailableError() from exc
        return self._client

    def put(self, organization_id: UUID, project_id: UUID, filename: str, data: bytes) -> StoredObject:
        safe_name = Path(filename.replace("\\", "/")).name or "upload.xlsx"
        key = PurePosixPath(str(organization_id), str(project_id), str(uuid4()), safe_name).as_posix()
        client = self._get_client()
        try:
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as exc:
            raise StorageUnavailableError() from exc
        return StoredObject(key=key, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

    def get(self, key: str) -> bytes:
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise StorageUnavailableError() from exc

    def delete(self, key: str) -> None:
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise StorageUnavailableError() from exc

    def presign_put(self, key: str, content_type: str, expires_in: int = 900) -> str | None:
        client = self._get_client()
        try:
            return client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=expires_in,
            )
        except Exception:
            return None

    def exists(self, key: str) -> bool:
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            response = getattr(exc, "response", {})
            metadata = response.get("ResponseMetadata", {})
            if metadata.get("HTTPStatusCode") == 404:
                return False
            raise StorageUnavailableError() from exc
        return True

    def is_ready(self) -> bool:
        try:
            self._get_client().head_bucket(Bucket=self.bucket)
        except Exception:
            return False
        return True
