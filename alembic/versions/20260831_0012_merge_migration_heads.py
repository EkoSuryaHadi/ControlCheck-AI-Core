"""Merge telemetry and health migration heads.

Revision ID: 20260831_0012
Revises: 20260825_0011, 20260906_0001
"""

from collections.abc import Sequence


revision: str = "20260831_0012"
down_revision: tuple[str, str] = ("20260825_0011", "20260906_0001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
