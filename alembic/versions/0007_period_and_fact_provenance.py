"""Persist programme periods and complete source-fact derivation provenance.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("metric_definitions") as batch_op:
        batch_op.add_column(sa.Column("period_semantics", sa.String(length=40), nullable=True))
        batch_op.create_index(
            "ix_metric_definitions_period_semantics", ["period_semantics"], unique=False
        )

    op.create_table(
        "company_programme_memberships",
        sa.Column("id", sa.String(length=48), nullable=False),
        sa.Column("raw_submission_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("programme_start_date", sa.Date(), nullable=False),
        sa.Column("submitted_period_label", sa.String(length=100), nullable=False),
        sa.Column("source_cell", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_submission_id"], ["raw_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "raw_submission_id",
            "company_id",
            name="uq_programme_membership_submission_company",
        ),
    )
    op.create_index(
        "ix_company_programme_memberships_raw_submission_id",
        "company_programme_memberships",
        ["raw_submission_id"],
    )
    op.create_index(
        "ix_company_programme_memberships_company_id",
        "company_programme_memberships",
        ["company_id"],
    )
    op.create_index(
        "ix_company_programme_memberships_programme_start_date",
        "company_programme_memberships",
        ["programme_start_date"],
    )

    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.add_column(sa.Column("programme_start_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("derivation_contract_version", sa.String(length=50), nullable=True)
        )
    op.execute(
        "UPDATE source_snapshots SET derivation_contract_version = "
        "'source-derivation-v1' WHERE derivation_sha256 IS NOT NULL"
    )

    with op.batch_alter_table("evidence_facts") as batch_op:
        batch_op.add_column(sa.Column("structured_locator_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("extraction_method", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("extraction_schema_version", sa.String(length=100), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence_facts") as batch_op:
        batch_op.drop_column("extraction_schema_version")
        batch_op.drop_column("extraction_method")
        batch_op.drop_column("structured_locator_json")
    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.drop_column("derivation_contract_version")
        batch_op.drop_column("programme_start_date")
    op.drop_table("company_programme_memberships")
    with op.batch_alter_table("metric_definitions") as batch_op:
        batch_op.drop_index("ix_metric_definitions_period_semantics")
        batch_op.drop_column("period_semantics")
