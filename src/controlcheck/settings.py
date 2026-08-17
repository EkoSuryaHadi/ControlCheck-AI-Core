from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PersistenceSettings:
    database_url: str
    upload_root: Path

    @classmethod
    def from_env(cls) -> "PersistenceSettings":
        database_url = os.environ.get("CONTROLCHECK_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("CONTROLCHECK_DATABASE_URL is required for durable API endpoints")
        return cls(
            database_url=database_url,
            upload_root=Path(os.environ.get("CONTROLCHECK_UPLOAD_ROOT", "var/uploads")),
        )
