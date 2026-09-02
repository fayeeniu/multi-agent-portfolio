"""Add versioned ingestion and reviewed company identity foundations.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[str]:
    return sa.Column("id", sa.String(length=48), nullable=False)


def _created_at() -> sa.Column[datetime]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    with op.batch_alter_table(
        "companies",
        recreate="always",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch_op:
        batch_op.drop_constraint("uq_companies_normalized_name", type_="unique")

    with op.batch_alter_table("raw_submissions") as batch_op:
        batch_op.add_column(sa.Column("reporting_cutoff", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("profile_key", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("profile_version", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("catalogue_version", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("catalogue_sha256", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "import_summary_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )

    op.create_table(
        "catalogue_versions",
        _id(),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("definition_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index("ix_catalogue_versions_sha256", "catalogue_versions", ["sha256"])
    op.create_index("ix_catalogue_versions_version", "catalogue_versions", ["version"])

    op.create_table(
        "company_identifiers",
        _id(),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("scheme", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("source_key", sa.String(length=100), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme", "normalized_value", name="uq_identifier_scheme_value"),
        sa.UniqueConstraint(
            "company_id", "scheme", "normalized_value", name="uq_company_identifier"
        ),
    )
    op.create_index("ix_company_identifiers_company_id", "company_identifiers", ["company_id"])
    op.create_index(
        "ix_company_identifiers_normalized_value",
        "company_identifiers",
        ["normalized_value"],
    )
    op.create_index("ix_company_identifiers_scheme", "company_identifiers", ["scheme"])

    op.create_table(
        "identity_candidates",
        _id(),
        sa.Column("raw_submission_id", sa.String(length=48), nullable=False),
        sa.Column("imported_company_id", sa.String(length=48), nullable=False),
        sa.Column("candidate_company_id", sa.String(length=48), nullable=True),
        sa.Column("submitted_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("identifier_scheme", sa.String(length=64), nullable=True),
        sa.Column("submitted_identifier", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["candidate_company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["imported_company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_submission_id"], ["raw_submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "raw_submission_id",
            "imported_company_id",
            "submitted_identifier",
            name="uq_identity_candidate_submission_value",
        ),
    )
    op.create_index(
        "ix_identity_candidates_candidate_company_id",
        "identity_candidates",
        ["candidate_company_id"],
    )
    op.create_index(
        "ix_identity_candidates_imported_company_id",
        "identity_candidates",
        ["imported_company_id"],
    )
    op.create_index(
        "ix_identity_candidates_normalized_name", "identity_candidates", ["normalized_name"]
    )
    op.create_index(
        "ix_identity_candidates_raw_submission_id",
        "identity_candidates",
        ["raw_submission_id"],
    )
    op.create_index("ix_identity_candidates_status", "identity_candidates", ["status"])

    op.create_table(
        "identity_decisions",
        _id(),
        sa.Column("candidate_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["candidate_id"], ["identity_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
    )
    op.create_index("ix_identity_decisions_candidate_id", "identity_decisions", ["candidate_id"])
    op.create_index("ix_identity_decisions_company_id", "identity_decisions", ["company_id"])

    op.create_table(
        "observation_narratives",
        _id(),
        sa.Column("observation_id", sa.String(length=48), nullable=True),
        sa.Column("raw_submission_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("parent_metric_key", sa.String(length=100), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("source_cell", sa.String(length=32), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_submission_id"], ["raw_submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "raw_submission_id",
            "company_id",
            "parent_metric_key",
            "source_cell",
            name="uq_observation_narrative_source",
        ),
    )
    op.create_index(
        "ix_observation_narratives_company_id", "observation_narratives", ["company_id"]
    )
    op.create_index(
        "ix_observation_narratives_observation_id",
        "observation_narratives",
        ["observation_id"],
    )
    op.create_index(
        "ix_observation_narratives_parent_metric_key",
        "observation_narratives",
        ["parent_metric_key"],
    )
    op.create_index(
        "ix_observation_narratives_raw_submission_id",
        "observation_narratives",
        ["raw_submission_id"],
    )

    connection = op.get_bind()
    legacy_rows = list(
        connection.execute(
            sa.text(
                "SELECT id, external_id, created_at FROM companies "
                "WHERE external_id IS NOT NULL AND trim(external_id) <> ''"
            )
        ).mappings()
    )
    normalized_counts = Counter(str(row["external_id"]).strip().upper() for row in legacy_rows)
    for row in legacy_rows:
        value = str(row["external_id"]).strip()
        normalized = value.upper()
        if normalized_counts[normalized] > 1:
            connection.execute(
                sa.text(
                    "UPDATE companies SET resolution_status = 'unresolved' WHERE id = :company_id"
                ),
                {"company_id": row["id"]},
            )
            continue
        digest = hashlib.sha256(f"legacy:{row['id']}:{normalized}".encode()).hexdigest()[:32]
        connection.execute(
            sa.text(
                "INSERT INTO company_identifiers "
                "(id, company_id, scheme, value, normalized_value, source_key, valid_from, "
                "valid_to, reviewed, created_at) "
                "VALUES (:id, :company_id, 'legacy', :value, :normalized, NULL, NULL, NULL, 1, "
                ":created_at)"
            ),
            {
                "id": f"cid_{digest}",
                "company_id": row["id"],
                "value": value,
                "normalized": normalized,
                "created_at": row["created_at"],
            },
        )


def downgrade() -> None:
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT normalized_name, COUNT(*) AS duplicate_count FROM companies "
                "GROUP BY normalized_name HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError("Downgrade to 0001 would violate its unique normalized-name contract.")
    op.drop_table("observation_narratives")
    op.drop_table("identity_decisions")
    op.drop_table("identity_candidates")
    op.drop_table("company_identifiers")
    op.drop_table("catalogue_versions")

    with op.batch_alter_table("raw_submissions") as batch_op:
        batch_op.drop_column("import_summary_json")
        batch_op.drop_column("catalogue_sha256")
        batch_op.drop_column("catalogue_version")
        batch_op.drop_column("profile_version")
        batch_op.drop_column("profile_key")
        batch_op.drop_column("reporting_cutoff")

    with op.batch_alter_table("companies", recreate="always") as batch_op:
        batch_op.create_unique_constraint("uq_companies_normalized_name", ["normalized_name"])
