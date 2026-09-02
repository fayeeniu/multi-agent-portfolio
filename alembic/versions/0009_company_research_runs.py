"""Add persisted live company-research runs and cited claims.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic.util import CommandError

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[str]:
    return sa.Column("id", sa.String(length=48), nullable=False)


def _created_at() -> sa.Column[object]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "company_research_runs",
        _id(),
        sa.Column("research_case_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reporting_cutoff", sa.Date(), nullable=False),
        sa.Column("source_policy_version", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("budgets_json", sa.JSON(), nullable=False),
        sa.Column("usage_json", sa.JSON(), nullable=False),
        sa.Column("coverage_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("cancelled_by", sa.String(length=255), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_case_id"], ["research_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_fingerprint"),
    )
    for column in (
        "research_case_id",
        "company_id",
        "request_fingerprint",
        "reporting_cutoff",
        "status",
    ):
        op.create_index(f"ix_company_research_runs_{column}", "company_research_runs", [column])

    op.create_table(
        "company_research_tasks",
        _id(),
        sa.Column("research_run_id", sa.String(length=48), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["research_run_id"], ["company_research_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_fingerprint"),
        sa.UniqueConstraint("research_run_id", "capability", name="uq_company_research_task"),
    )
    for column in ("research_run_id", "capability", "request_fingerprint", "status"):
        op.create_index(f"ix_company_research_tasks_{column}", "company_research_tasks", [column])

    op.create_table(
        "company_research_task_attempts",
        _id(),
        sa.Column("research_task_id", sa.String(length=48), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("tool_calls", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["research_task_id"], ["company_research_tasks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "research_task_id", "attempt_number", name="uq_company_research_task_attempt"
        ),
    )
    op.create_index(
        "ix_company_research_task_attempts_research_task_id",
        "company_research_task_attempts",
        ["research_task_id"],
    )
    op.create_index(
        "ix_company_research_task_attempts_status",
        "company_research_task_attempts",
        ["status"],
    )

    op.create_table(
        "company_research_sources",
        _id(),
        sa.Column("research_run_id", sa.String(length=48), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("publisher_domain", sa.String(length=255), nullable=False),
        sa.Column("source_tier", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("media_type", sa.String(length=100), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("raw_sha256", sa.String(length=64), nullable=True),
        sa.Column("snapshot_path", sa.Text(), nullable=True),
        sa.Column("snapshot_kind", sa.String(length=40), nullable=True),
        sa.Column("redaction_count", sa.Integer(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["research_run_id"], ["company_research_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_run_id", "url", name="uq_company_research_source_url"),
    )
    for column in (
        "research_run_id",
        "publisher_domain",
        "source_tier",
        "status",
        "raw_sha256",
        "text_sha256",
    ):
        op.create_index(
            f"ix_company_research_sources_{column}", "company_research_sources", [column]
        )

    op.create_table(
        "company_research_claims",
        _id(),
        sa.Column("research_run_id", sa.String(length=48), nullable=False),
        sa.Column("research_source_id", sa.String(length=48), nullable=False),
        sa.Column("claim_hash", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("subject_key", sa.String(length=100), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("event_date", sa.String(length=32), nullable=True),
        sa.Column("amount", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("perspective", sa.String(length=40), nullable=False),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        sa.Column("extraction_method", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["research_run_id"], ["company_research_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["research_source_id"], ["company_research_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_hash"),
    )
    for column in (
        "research_run_id",
        "research_source_id",
        "claim_hash",
        "category",
        "subject_key",
        "verification_status",
    ):
        op.create_index(f"ix_company_research_claims_{column}", "company_research_claims", [column])

    with op.batch_alter_table("profile_versions") as batch_op:
        batch_op.add_column(sa.Column("research_run_id", sa.String(length=48), nullable=True))
        batch_op.create_foreign_key(
            "fk_profile_versions_research_run_id",
            "company_research_runs",
            ["research_run_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_profile_versions_research_run_id", ["research_run_id"], unique=True
        )


def downgrade() -> None:
    connection = op.get_bind()
    populated = [
        table
        for table in (
            "company_research_claims",
            "company_research_sources",
            "company_research_task_attempts",
            "company_research_tasks",
            "company_research_runs",
        )
        if connection.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None
    ]
    linked_profile = connection.execute(
        sa.text("SELECT 1 FROM profile_versions WHERE research_run_id IS NOT NULL LIMIT 1")
    ).first()
    if linked_profile is not None:
        populated.append("profile_versions.research_run_id")
    if populated:
        raise CommandError(
            "Revision 0009 contains live company-research state and cannot be downgraded "
            "without data loss; no schema mutation was performed."
        )

    with op.batch_alter_table("profile_versions") as batch_op:
        batch_op.drop_index("ix_profile_versions_research_run_id")
        batch_op.drop_constraint("fk_profile_versions_research_run_id", type_="foreignkey")
        batch_op.drop_column("research_run_id")
    op.drop_table("company_research_claims")
    op.drop_table("company_research_sources")
    op.drop_table("company_research_task_attempts")
    op.drop_table("company_research_tasks")
    op.drop_table("company_research_runs")
