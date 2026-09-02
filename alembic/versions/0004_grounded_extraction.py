"""Persist exact grounding and abstention for strict extractions.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.add_column(sa.Column("evidence_span", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("abstain_reason", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.drop_column("abstain_reason")
        batch_op.drop_column("evidence_span")
