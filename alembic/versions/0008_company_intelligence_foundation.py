"""Add the offline company-intelligence case and intake foundation.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic.util import CommandError

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[str]:
    return sa.Column("id", sa.String(length=48), nullable=False)


def _created_at() -> sa.Column[object]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(sa.Column("entity_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("jurisdiction", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("lifecycle_status", sa.String(length=32), nullable=True))
        batch_op.create_index("ix_companies_entity_type", ["entity_type"], unique=False)
        batch_op.create_index("ix_companies_jurisdiction", ["jurisdiction"], unique=False)
        batch_op.create_index("ix_companies_lifecycle_status", ["lifecycle_status"], unique=False)

    op.create_table(
        "research_templates",
        _id(),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_research_templates_key", "research_templates", ["key"])

    op.create_table(
        "research_template_versions",
        _id(),
        sa.Column("template_id", sa.String(length=48), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("required_capabilities_json", sa.JSON(), nullable=False),
        sa.Column("optional_capabilities_json", sa.JSON(), nullable=False),
        sa.Column("claim_keys_json", sa.JSON(), nullable=False),
        sa.Column("budgets_json", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["research_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256"),
        sa.UniqueConstraint("template_id", "version", name="uq_research_template_version"),
    )
    op.create_index(
        "ix_research_template_versions_template_id",
        "research_template_versions",
        ["template_id"],
    )
    op.create_index(
        "ix_research_template_versions_sha256",
        "research_template_versions",
        ["sha256"],
    )

    op.create_table(
        "research_cases",
        _id(),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("template_version_id", sa.String(length=48), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["research_template_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "purpose",
            "template_version_id",
            "classification",
            name="uq_research_case_scope",
        ),
    )
    op.create_index("ix_research_cases_company_id", "research_cases", ["company_id"])
    op.create_index(
        "ix_research_cases_template_version_id",
        "research_cases",
        ["template_version_id"],
    )
    op.create_index("ix_research_cases_classification", "research_cases", ["classification"])
    op.create_index("ix_research_cases_status", "research_cases", ["status"])

    op.create_table(
        "intake_artifacts",
        _id(),
        sa.Column("research_case_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("submitted_value_json", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("snapshot_path", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_case_id"], ["research_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index(
        "ix_intake_artifacts_research_case_id",
        "intake_artifacts",
        ["research_case_id"],
    )
    op.create_index("ix_intake_artifacts_company_id", "intake_artifacts", ["company_id"])
    op.create_index("ix_intake_artifacts_kind", "intake_artifacts", ["kind"])
    op.create_index("ix_intake_artifacts_fingerprint", "intake_artifacts", ["fingerprint"])
    op.create_index("ix_intake_artifacts_content_sha256", "intake_artifacts", ["content_sha256"])
    op.create_index("ix_intake_artifacts_classification", "intake_artifacts", ["classification"])

    op.create_table(
        "company_domains",
        _id(),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("normalized_domain", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "normalized_domain", name="uq_company_domain"),
    )
    op.create_index("ix_company_domains_company_id", "company_domains", ["company_id"])
    op.create_index(
        "ix_company_domains_normalized_domain", "company_domains", ["normalized_domain"]
    )
    op.create_index("ix_company_domains_status", "company_domains", ["status"])

    op.create_table(
        "company_domain_decisions",
        _id(),
        sa.Column("company_domain_id", sa.String(length=48), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_domain_id"], ["company_domains.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_domain_decisions_company_domain_id",
        "company_domain_decisions",
        ["company_domain_id"],
    )

    op.create_table(
        "company_identifier_decisions",
        _id(),
        sa.Column("company_identifier_id", sa.String(length=48), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["company_identifier_id"], ["company_identifiers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_identifier_decisions_company_identifier_id",
        "company_identifier_decisions",
        ["company_identifier_id"],
    )

    op.create_table(
        "profile_versions",
        _id(),
        sa.Column("research_case_id", sa.String(length=48), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["research_case_id"], ["research_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_case_id", "version", name="uq_profile_case_version"),
    )
    op.create_index(
        "ix_profile_versions_research_case_id", "profile_versions", ["research_case_id"]
    )
    op.create_index("ix_profile_versions_status", "profile_versions", ["status"])
    op.create_index("ix_profile_versions_content_sha256", "profile_versions", ["content_sha256"])


def downgrade() -> None:
    connection = op.get_bind()
    populated = [
        table
        for table in (
            "profile_versions",
            "company_identifier_decisions",
            "company_domain_decisions",
            "company_domains",
            "intake_artifacts",
            "research_cases",
            "research_template_versions",
            "research_templates",
        )
        if connection.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None
    ]
    company_metadata_exists = (
        connection.execute(
            sa.text(
                "SELECT 1 FROM companies WHERE entity_type IS NOT NULL "
                "OR jurisdiction IS NOT NULL OR lifecycle_status IS NOT NULL LIMIT 1"
            )
        ).first()
        is not None
    )
    if company_metadata_exists:
        populated.append("companies.company-intelligence fields")
    if populated:
        raise CommandError(
            "Revision 0008 contains company-intelligence records and cannot be downgraded "
            "without data loss; no schema mutation was performed."
        )

    op.drop_table("profile_versions")
    op.drop_table("company_identifier_decisions")
    op.drop_table("company_domain_decisions")
    op.drop_table("company_domains")
    op.drop_table("intake_artifacts")
    op.drop_table("research_cases")
    op.drop_table("research_template_versions")
    op.drop_table("research_templates")
    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_index("ix_companies_lifecycle_status")
        batch_op.drop_index("ix_companies_jurisdiction")
        batch_op.drop_index("ix_companies_entity_type")
        batch_op.drop_column("lifecycle_status")
        batch_op.drop_column("jurisdiction")
        batch_op.drop_column("entity_type")
