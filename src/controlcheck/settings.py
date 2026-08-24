from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID


DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SUPPORTED_ENVIRONMENTS = {"development", "test", "production"}


def _parse_csv(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return ()
    values = tuple(value.strip() for value in raw.split(","))
    if any(not value for value in values):
        raise RuntimeError(f"{name} cannot contain empty values")
    return values


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise RuntimeError(f"{name} must be true or false")


def _parse_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else int(raw.strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _is_https_origin(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and parsed.path == ""
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
        and "*" not in value
    )


@dataclass(frozen=True)
class ApplicationSettings:
    environment: str
    database_url: str | None
    upload_root: Path
    catalogue_path: Path | None
    organization_id: UUID | None
    api_key: str | None
    trusted_hosts: tuple[str, ...]
    cors_origins: tuple[str, ...]
    enable_docs: bool
    max_upload_bytes: int

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @classmethod
    def from_env(cls) -> "ApplicationSettings":
        environment = os.environ.get("CONTROLCHECK_ENV", "development").strip()
        if environment not in SUPPORTED_ENVIRONMENTS:
            allowed = ", ".join(sorted(SUPPORTED_ENVIRONMENTS))
            raise RuntimeError(f"CONTROLCHECK_ENV must be one of: {allowed}")

        database_url = os.environ.get("CONTROLCHECK_DATABASE_URL", "").strip() or None
        upload_root = Path(os.environ.get("CONTROLCHECK_UPLOAD_ROOT", "var/uploads").strip())
        catalogue_raw = os.environ.get("CONTROLCHECK_CATALOGUE", "").strip()
        catalogue_path = Path(catalogue_raw) if catalogue_raw else None

        organization_raw = os.environ.get("CONTROLCHECK_ORGANIZATION_ID", "").strip()
        try:
            organization_id = UUID(organization_raw) if organization_raw else None
        except ValueError as exc:
            raise RuntimeError("CONTROLCHECK_ORGANIZATION_ID must be a UUID") from exc

        api_key = os.environ.get("CONTROLCHECK_API_KEY", "").strip() or None
        trusted_hosts = _parse_csv("CONTROLCHECK_TRUSTED_HOSTS")
        cors_origins = _parse_csv("CONTROLCHECK_CORS_ORIGINS")
        enable_docs = _parse_bool(
            "CONTROLCHECK_ENABLE_DOCS", default=environment != "production"
        )
        max_upload_bytes = _parse_positive_int(
            "CONTROLCHECK_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES
        )

        if environment == "production":
            if database_url is None:
                raise RuntimeError("CONTROLCHECK_DATABASE_URL is required in production")
            if not upload_root.is_absolute():
                raise RuntimeError("CONTROLCHECK_UPLOAD_ROOT must be absolute in production")
            if catalogue_path is None or not catalogue_path.is_file() or not os.access(catalogue_path, os.R_OK):
                raise RuntimeError(
                    "CONTROLCHECK_CATALOGUE must reference a readable file in production"
                )
            if organization_id is None:
                raise RuntimeError("CONTROLCHECK_ORGANIZATION_ID is required in production")
            if api_key is None or len(api_key) < 32:
                raise RuntimeError(
                    "CONTROLCHECK_API_KEY must contain at least 32 characters in production"
                )
            if not trusted_hosts or any("*" in host for host in trusted_hosts):
                raise RuntimeError(
                    "CONTROLCHECK_TRUSTED_HOSTS must contain exact hosts in production"
                )
            if any(not _is_https_origin(origin) for origin in cors_origins):
                raise RuntimeError(
                    "CONTROLCHECK_CORS_ORIGINS must contain exact HTTPS origins in production"
                )

        return cls(
            environment=environment,
            database_url=database_url,
            upload_root=upload_root,
            catalogue_path=catalogue_path,
            organization_id=organization_id,
            api_key=api_key,
            trusted_hosts=trusted_hosts,
            cors_origins=cors_origins,
            enable_docs=enable_docs,
            max_upload_bytes=max_upload_bytes,
        )


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
