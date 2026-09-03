from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    sha256: str


class FileStorage(Protocol):
    def put(self, organization_id: UUID, project_id: UUID, filename: str, data: bytes) -> StoredObject: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def is_ready(self) -> bool: ...
    def presign_put(self, key: str, content_type: str, expires_in: int = 900) -> str | None:
        """Return a presigned PUT URL for browser-to-storage upload, or None when
        the backend does not support presigning (e.g. local disk)."""
        ...


class LocalFileStorage:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def _resolve_key(self, key: str) -> Path:
        target = (self.root / Path(*PurePosixPath(key).parts)).resolve()
        if self.root != target and self.root not in target.parents:
            raise ValueError("Storage key resolves outside configured root")
        return target

    def put(self, organization_id: UUID, project_id: UUID, filename: str, data: bytes) -> StoredObject:
        safe_name = Path(filename.replace("\\", "/")).name or "upload.xlsx"
        key = PurePosixPath(str(organization_id), str(project_id), str(uuid4()), safe_name).as_posix()
        target = self._resolve_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
        return StoredObject(key=key, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

    def get(self, key: str) -> bytes:
        return self._resolve_key(key).read_bytes()

    def delete(self, key: str) -> None:
        target = self._resolve_key(key)
        target.unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._resolve_key(key).is_file()

    def presign_put(self, key: str, content_type: str, expires_in: int = 900) -> str | None:
        return None

    def is_ready(self) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return self.root.is_dir() and os.access(self.root, os.W_OK)
