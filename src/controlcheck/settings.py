from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .limits import PUBLIC_BETA_MAX_UPLOAD_BYTES


_APPLICATION_ENVIRONMENTS = {"development", "test", "production"}
_VERCEL_ENVIRONMENTS = {"development", "preview", "production"}


def _normalized_environment(name: str, allowed: set[str]) -> str | None:
    if name not in os.environ:
        return None
    value = os.environ[name].strip().lower()
    if not value or value not in allowed:
        raise ValueError(f"Invalid {name} environment mode")
    return value


def _runtime_environment() -> str:
    """Resolve application mode with production platform signals failing closed.

    Vercel's platform environment is authoritative: production deployments always
    use the strict production contract, while Preview deployments stay isolated
    from production-only secret/storage requirements even when project-level
    environment variables contain ``CONTROLCHECK_ENV=production``.

    Outside Vercel, CONTROLCHECK_ENV takes precedence over legacy ENV. Unknown
    serverless runtimes still fail closed to the production contract.
    """
    explicit = _normalized_environment(
        "CONTROLCHECK_ENV", _APPLICATION_ENVIRONMENTS
    )
    if explicit is None:
        explicit = _normalized_environment("ENV", _APPLICATION_ENVIRONMENTS)
    vercel_env = _normalized_environment("VERCEL_ENV", _VERCEL_ENVIRONMENTS)

    if vercel_env == "production":
        return "production"
    if vercel_env in {"development", "preview"}:
        return "development"
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "production"
    if os.environ.get("RENDER"):
        return "production"
    if os.environ.get("VERCEL") and vercel_env is None:
        return "production"
    if explicit is not None:
        return explicit
    return "development"


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
    trusted_hosts: list[str]
    max_upload_bytes: int
    storage_backend: str
    s3_bucket: str
    s3_region: str
    s3_endpoint_url: str | None

    @classmethod
    def from_env(cls) -> "ProductionSettings":
        env = _runtime_environment()
        jwt_secret = os.environ.get("CONTROLCHECK_JWT_SECRET", "")
        database_url = _database_url_from_env()
        cors_raw = os.environ.get("CONTROLCHECK_CORS_ORIGINS", "*")
        cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
        trusted_hosts_raw = os.environ.get("CONTROLCHECK_TRUSTED_HOSTS", "*")
        trusted_hosts = [host.strip() for host in trusted_hosts_raw.split(",") if host.strip()]

        # Vercel preview URLs are generated dynamically per commit and branch. Allow
        # only the platform preview domain family when we are explicitly in Preview;
        # Vercel Production remains subject to the strict explicit-host contract below.
        if os.environ.get("VERCEL_ENV", "").strip().lower() == "preview":
            trusted_hosts = list(dict.fromkeys([*trusted_hosts, "*.vercel.app"]))

        max_upload = int(
            os.environ.get(
                "CONTROLCHECK_MAX_UPLOAD_BYTES",
                PUBLIC_BETA_MAX_UPLOAD_BYTES,
            )
        )
        storage_backend = os.environ.get(
            "CONTROLCHECK_STORAGE_BACKEND", "local"
        ).strip().lower()
        s3_bucket = os.environ.get("CONTROLCHECK_S3_BUCKET", "").strip()
        s3_region = os.environ.get("CONTROLCHECK_S3_REGION", "ap-southeast-1").strip()
        s3_endpoint_url = os.environ.get("CONTROLCHECK_S3_ENDPOINT_URL") or None

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
            if not cors_origins or any("*" in origin for origin in cors_origins):
                raise ValueError(
                    "INSECURE CONFIGURATION: production CORS origins must be explicit."
                )
            if not trusted_hosts or any("*" in host for host in trusted_hosts):
                raise ValueError(
                    "INSECURE CONFIGURATION: production trusted hosts must be explicit."
                )
            if storage_backend not in {"local", "s3"}:
                raise ValueError(
                    "INSECURE CONFIGURATION: production storage backend must be local or s3."
                )
            is_serverless = bool(
                os.environ.get("VERCEL")
                or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
                or os.environ.get("RENDER")
            )
            if is_serverless and storage_backend == "local":
                raise ValueError(
                    "INSECURE CONFIGURATION: serverless production requires durable storage."
                )
            if storage_backend == "s3" and not s3_bucket:
                raise ValueError(
                    "INSECURE CONFIGURATION: CONTROLCHECK_S3_BUCKET is required for S3 storage."
                )

        return cls(
            env=env,
            jwt_secret=jwt_secret,
            database_url=database_url,
            cors_origins=cors_origins,
            trusted_hosts=trusted_hosts,
            max_upload_bytes=max_upload,
            storage_backend=storage_backend,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            s3_endpoint_url=s3_endpoint_url,
        )