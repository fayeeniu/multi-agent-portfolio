"""Add reviewed group scope and hybrid document provenance.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic.util import CommandError

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_relationships",
        sa.Column("id", sa.String(length=48), nullable=False),
        sa.Column("subject_company_id", sa.String(length=48), nullable=False),
        sa.Column("related_company_id", sa.String(length=48), nullable=False),
        sa.Column("relationship_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("proposed_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["related_company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_company_id",
            "related_company_id",
            "relationship_type",
            name="uq_company_relationship_scope",
        ),
    )
    for column in ("subject_company_id", "related_company_id", "relationship_type", "status"):
        op.create_index(f"ix_company_relationships_{column}", "company_relationships", [column])

    op.create_table(
        "company_relationship_decisions",
        sa.Column("id", sa.String(length=48), nullable=False),
        sa.Column("company_relationship_id", sa.String(length=48), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_relationship_id"], ["company_relationships.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_relationship_id"),
    )
    op.create_index(
        "ix_company_relationship_decisions_company_relationship_id",
        "company_relationship_decisions",
        ["company_relationship_id"],
    )

    with op.batch_alter_table("company_research_sources") as batch_op:
        batch_op.add_column(sa.Column("intake_artifact_id", sa.String(length=48), nullable=True))
        batch_op.add_column(
            sa.Column(
                "origin", sa.String(length=40), nullable=False, server_default="public_web"
            )
        )
        batch_op.add_column(
            sa.Column(
                "entity_scope", sa.String(length=40), nullable=False, server_default="legal_entity"
            )
        )
        batch_op.create_foreign_key(
            "fk_company_research_sources_intake_artifact",
            "intake_artifacts",
            ["intake_artifact_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_company_research_sources_intake_artifact_id", ["intake_artifact_id"]
        )
        batch_op.create_index("ix_company_research_sources_origin", ["origin"])
        batch_op.create_index("ix_company_research_sources_entity_scope", ["entity_scope"])

    with op.batch_alter_table("company_research_claims") as batch_op:
        batch_op.add_column(
            sa.Column(
                "entity_scope", sa.String(length=40), nullable=False, server_default="legal_entity"
            )
        )
        batch_op.create_index("ix_company_research_claims_entity_scope", ["entity_scope"])


def downgrade() -> None:
    connection = op.get_bind()
    relationship_data = connection.execute(
        sa.text("SELECT 1 FROM company_relationships LIMIT 1")
    ).first()
    scoped_data = connection.execute(
        sa.text(
            "SELECT 1 FROM company_research_sources WHERE intake_artifact_id IS NOT NULL "
            "OR origin != 'public_web' OR entity_scope != 'legal_entity' LIMIT 1"
        )
    ).first()
    scoped_claims = connection.execute(
        sa.text(
            "SELECT 1 FROM company_research_claims WHERE entity_scope != 'legal_entity' LIMIT 1"
        )
    ).first()
    if relationship_data or scoped_data or scoped_claims:
        raise CommandError(
            "Revision 0010 contains hybrid or scoped evidence and cannot be downgraded "
            "without data loss; no schema mutation was performed."
        )

    with op.batch_alter_table("company_research_claims") as batch_op:
        batch_op.drop_index("ix_company_research_claims_entity_scope")
        batch_op.drop_column("entity_scope")
    with op.batch_alter_table("company_research_sources") as batch_op:
        batch_op.drop_index("ix_company_research_sources_entity_scope")
        batch_op.drop_index("ix_company_research_sources_origin")
        batch_op.drop_index("ix_company_research_sources_intake_artifact_id")
        batch_op.drop_constraint(
            "fk_company_research_sources_intake_artifact", type_="foreignkey"
        )
        batch_op.drop_column("entity_scope")
        batch_op.drop_column("origin")
        batch_op.drop_column("intake_artifact_id")
    op.drop_table("company_relationship_decisions")
    op.drop_table("company_relationships")
