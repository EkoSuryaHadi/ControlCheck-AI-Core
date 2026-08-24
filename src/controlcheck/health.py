from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .storage import FileStorage


logger = logging.getLogger(__name__)


def database_ready(session_factory: sessionmaker[Session] | None) -> bool:
    if session_factory is None:
        return False
    with session_factory() as session:
        session.execute(select(1))
    return True


def storage_ready(storage: FileStorage | None) -> bool:
    return storage is not None and storage.ready()


def catalogue_ready(catalogue_path: Path) -> bool:
    return catalogue_path.is_file() and os.access(catalogue_path, os.R_OK)


def check_readiness(
    session_factory: sessionmaker[Session] | None,
    storage: FileStorage | None,
    catalogue_path: Path,
) -> bool:
    try:
        return (
            database_ready(session_factory)
            and storage_ready(storage)
            and catalogue_ready(catalogue_path)
        )
    except Exception:
        logger.warning("A production readiness dependency is unavailable")
        return False
