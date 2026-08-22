from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    # Normalize postgresql:// to postgresql+psycopg:// for psycopg v3 compatibility
    normalized_url = database_url
    if normalized_url.startswith("postgresql://"):
        normalized_url = "postgresql+psycopg://" + normalized_url[len("postgresql://"):]
    elif normalized_url.startswith("postgres://"):
        normalized_url = "postgresql+psycopg://" + normalized_url[len("postgres://"):]

    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    
    if is_serverless:
        # In serverless environments, avoid pooling issues across ephemeral invocations
        engine = create_engine(
            normalized_url,
            poolclass=NullPool,
            connect_args={"connect_timeout": 10},
        )
    else:
        engine = create_engine(normalized_url, pool_pre_ping=True)
        
    return sessionmaker(bind=engine, expire_on_commit=False)
