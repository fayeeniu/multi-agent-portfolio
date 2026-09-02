"""Persist canonical source-result derivation hashes.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.add_column(sa.Column("derivation_sha256", sa.String(length=64), nullable=True))
        batch_op.create_index(
            "ix_source_snapshots_derivation_sha256",
            ["derivation_sha256"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.drop_index("ix_source_snapshots_derivation_sha256")
        batch_op.drop_column("derivation_sha256")
