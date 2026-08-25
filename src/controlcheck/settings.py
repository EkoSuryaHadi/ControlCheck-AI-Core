from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _database_url_from_env() -> str:
    """Resolve the durable database URL consistently across local and hosted runtimes.

    ControlCheck-specific configuration takes precedence, while the conventional
    DATABASE_URL name is accepted for Vercel/Postgres/Supabase integrations.
    """
    return (
        os.environ.get("CONTROLCHECK_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )


@dataclass(frozen=True)
class PersistenceSettings:
    database_url: str
    upload_root: Path

    @classmethod
    def from_env(cls) -> "PersistenceSettings":
        database_url = _database_url_from_env()
        if not database_url:
            raise RuntimeError(
                "CONTROLCHECK_DATABASE_URL or DATABASE_URL is required for durable API endpoints"
            )
        return cls(
            database_url=database_url,
            upload_root=Path(os.environ.get("CONTROLCHECK_UPLOAD_ROOT", "var/uploads")),
        )


@dataclass(frozen=True)
class ProductionSettings:
    env: str
    jwt_secret: str
    database_url: str
    cors_origins: list[str]
    max_upload_bytes: int
    storage_backend: str

    @classmethod
    def from_env(cls) -> "ProductionSettings":
        env = os.environ.get("CONTROLCHECK_ENV", os.environ.get("ENV", "development")).lower()
        jwt_secret = os.environ.get("CONTROLCHECK_JWT_SECRET", "dev-secret-key-change-in-production")
        database_url = _database_url_from_env()
        cors_raw = os.environ.get("CONTROLCHECK_CORS_ORIGINS", "*")
        cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
        max_upload = int(os.environ.get("CONTROLCHECK_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
        storage_backend = os.environ.get("CONTROLCHECK_STORAGE_BACKEND", "local")

        # In production mode, enforce security validations
        if env == "production":
            insecure_secrets = [
                "dev-secret-key-change-in-production",
                "change-this-in-production-use-openssl-rand-hex-32",
                "secret",
                "changeme",
            ]
            if jwt_secret in insecure_secrets or len(jwt_secret) < 32:
                raise ValueError(
                    "INSECURE CONFIGURATION: CONTROLCHECK_JWT_SECRET must be at least 32 characters "
                    "and cannot use known default values when running in production."
                )
            if not database_url:
                raise ValueError(
                    "INSECURE CONFIGURATION: a production database URL is required."
                )
            if not cors_origins or "*" in cors_origins:
                raise ValueError(
                    "INSECURE CONFIGURATION: production CORS origins must be explicit."
                )
            if storage_backend not in {"local", "s3"}:
                raise ValueError(
                    "INSECURE CONFIGURATION: production storage backend must be local or s3."
                )
            is_serverless = bool(
                os.environ.get("VERCEL")
                or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
            )
            if is_serverless and storage_backend == "local":
                raise ValueError(
                    "INSECURE CONFIGURATION: serverless production requires durable storage."
                )

        return cls(
            env=env,
            jwt_secret=jwt_secret,
            database_url=database_url,
            cors_origins=cors_origins,
            max_upload_bytes=max_upload,
            storage_backend=storage_backend,
        )
