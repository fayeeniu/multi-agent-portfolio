"""Add public-source snapshots, facts, events, quality, context, and export state.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[str]:
    return sa.Column("id", sa.String(length=48), nullable=False)


def _created_at() -> sa.Column[datetime]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "source_definitions",
        _id(),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("admitted", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "version", name="uq_source_definition_version"),
        sa.UniqueConstraint("manifest_sha256"),
    )
    op.create_index("ix_source_definitions_key", "source_definitions", ["key"])
    op.create_index(
        "ix_source_definitions_manifest_sha256", "source_definitions", ["manifest_sha256"]
    )

    op.create_table(
        "source_snapshots",
        _id(),
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("source_version", sa.String(length=50), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=True),
        sa.Column("identifier_scheme", sa.String(length=64), nullable=False),
        sa.Column("identifier_value", sa.String(length=255), nullable=False),
        sa.Column("reporting_cutoff", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("snapshot_path", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_key",
            "request_fingerprint",
            "sha256",
            name="uq_source_snapshot_request_content",
        ),
    )
    op.create_index("ix_source_snapshots_company_id", "source_snapshots", ["company_id"])
    op.create_index(
        "ix_source_snapshots_request_fingerprint",
        "source_snapshots",
        ["request_fingerprint"],
    )
    op.create_index("ix_source_snapshots_sha256", "source_snapshots", ["sha256"])
    op.create_index("ix_source_snapshots_source_key", "source_snapshots", ["source_key"])
    op.create_index("ix_source_snapshots_status", "source_snapshots", ["status"])

    with op.batch_alter_table("evidence_items", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("source_snapshot_id", sa.String(length=48), nullable=True))
        batch_op.add_column(sa.Column("temporal_status", sa.String(length=40), nullable=True))
        batch_op.create_foreign_key(
            "fk_evidence_items_source_snapshot_id",
            "source_snapshots",
            ["source_snapshot_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_evidence_items_source_snapshot_id", ["source_snapshot_id"], unique=False
        )
        batch_op.create_index(
            "ix_evidence_items_temporal_status", ["temporal_status"], unique=False
        )

    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.add_column(sa.Column("reporting_cutoff", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("evidence_contract_version", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("quality_contract_version", sa.String(length=100), nullable=True)
        )

    with op.batch_alter_table("extractions") as batch_op:
        batch_op.add_column(sa.Column("evidence_locator", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("confidence", sa.Numeric(8, 7), nullable=True))

    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(
            sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1")
        )

    op.create_table(
        "evidence_facts",
        _id(),
        sa.Column("source_snapshot_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("metric_definition_id", sa.String(length=48), nullable=True),
        sa.Column("fact_key", sa.String(length=100), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("temporal_status", sa.String(length=40), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"], ["metric_definitions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_snapshot_id", "fact_key", "source_locator", name="uq_snapshot_fact_locator"
        ),
    )
    op.create_index("ix_evidence_facts_company_id", "evidence_facts", ["company_id"])
    op.create_index("ix_evidence_facts_fact_key", "evidence_facts", ["fact_key"])
    op.create_index(
        "ix_evidence_facts_metric_definition_id",
        "evidence_facts",
        ["metric_definition_id"],
    )
    op.create_index(
        "ix_evidence_facts_source_snapshot_id", "evidence_facts", ["source_snapshot_id"]
    )
    op.create_index("ix_evidence_facts_temporal_status", "evidence_facts", ["temporal_status"])

    op.create_table(
        "company_events",
        _id(),
        sa.Column("event_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=48), nullable=True),
        sa.Column("raw_submission_id", sa.String(length=48), nullable=True),
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_stage", sa.String(length=64), nullable=True),
        sa.Column("public_identifier", sa.String(length=255), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_submission_id"], ["raw_submissions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_fingerprint"),
    )
    op.create_index("ix_company_events_company_id", "company_events", ["company_id"])
    op.create_index("ix_company_events_event_fingerprint", "company_events", ["event_fingerprint"])
    op.create_index("ix_company_events_event_type", "company_events", ["event_type"])
    op.create_index("ix_company_events_public_identifier", "company_events", ["public_identifier"])
    op.create_index("ix_company_events_raw_submission_id", "company_events", ["raw_submission_id"])
    op.create_index("ix_company_events_source_key", "company_events", ["source_key"])
    op.create_index(
        "ix_company_events_source_snapshot_id", "company_events", ["source_snapshot_id"]
    )

    op.create_table(
        "quality_contracts",
        _id(),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index("ix_quality_contracts_sha256", "quality_contracts", ["sha256"])
    op.create_index("ix_quality_contracts_version", "quality_contracts", ["version"])

    op.create_table(
        "quality_violations",
        _id(),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=True),
        sa.Column("metric_definition_id", sa.String(length=48), nullable=True),
        sa.Column("evidence_item_id", sa.String(length=48), nullable=True),
        sa.Column("source_snapshot_id", sa.String(length=48), nullable=True),
        sa.Column("rule_key", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"], ["metric_definitions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index("ix_quality_violations_company_id", "quality_violations", ["company_id"])
    op.create_index("ix_quality_violations_disposition", "quality_violations", ["disposition"])
    op.create_index(
        "ix_quality_violations_evidence_item_id", "quality_violations", ["evidence_item_id"]
    )
    op.create_index("ix_quality_violations_fingerprint", "quality_violations", ["fingerprint"])
    op.create_index(
        "ix_quality_violations_metric_definition_id",
        "quality_violations",
        ["metric_definition_id"],
    )
    op.create_index("ix_quality_violations_rule_key", "quality_violations", ["rule_key"])
    op.create_index("ix_quality_violations_run_id", "quality_violations", ["run_id"])
    op.create_index(
        "ix_quality_violations_source_snapshot_id",
        "quality_violations",
        ["source_snapshot_id"],
    )

    op.create_table(
        "extraction_attempts",
        _id(),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("evidence_item_id", sa.String(length=48), nullable=False),
        sa.Column("extraction_id", sa.String(length=48), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("escalation_cause", sa.String(length=100), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "evidence_item_id",
            "attempt_number",
            name="uq_extraction_attempt_number",
        ),
    )
    op.create_index(
        "ix_extraction_attempts_evidence_item_id",
        "extraction_attempts",
        ["evidence_item_id"],
    )
    op.create_index(
        "ix_extraction_attempts_extraction_id", "extraction_attempts", ["extraction_id"]
    )
    op.create_index("ix_extraction_attempts_run_id", "extraction_attempts", ["run_id"])
    op.create_index("ix_extraction_attempts_status", "extraction_attempts", ["status"])

    op.create_table(
        "context_statistics",
        _id(),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("metric_definition_id", sa.String(length=48), nullable=False),
        sa.Column("statistic_key", sa.String(length=100), nullable=False),
        sa.Column("cohort_definition_json", sa.JSON(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("reporting_cutoff", sa.Date(), nullable=False),
        sa.Column("source_versions_json", sa.JSON(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"], ["metric_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "metric_definition_id", "statistic_key", name="uq_context_statistic"
        ),
    )
    op.create_index(
        "ix_context_statistics_metric_definition_id",
        "context_statistics",
        ["metric_definition_id"],
    )
    op.create_index("ix_context_statistics_run_id", "context_statistics", ["run_id"])
    op.create_index("ix_context_statistics_status", "context_statistics", ["status"])

    op.create_table(
        "report_exports",
        _id(),
        sa.Column("report_id", sa.String(length=48), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("artifact_root", sa.Text(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_sha256"),
        sa.UniqueConstraint("report_id", "report_version", name="uq_report_export_version"),
    )
    op.create_index("ix_report_exports_manifest_sha256", "report_exports", ["manifest_sha256"])
    op.create_index("ix_report_exports_report_id", "report_exports", ["report_id"])
    op.create_index("ix_report_exports_status", "report_exports", ["status"])


def downgrade() -> None:
    op.drop_table("report_exports")
    op.drop_table("context_statistics")
    op.drop_table("extraction_attempts")
    op.drop_table("quality_violations")
    op.drop_table("quality_contracts")
    op.drop_table("company_events")
    op.drop_table("evidence_facts")

    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_column("lock_version")
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.drop_column("confidence")
        batch_op.drop_column("evidence_locator")
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_column("quality_contract_version")
        batch_op.drop_column("evidence_contract_version")
        batch_op.drop_column("reporting_cutoff")
    with op.batch_alter_table("evidence_items", recreate="always") as batch_op:
        batch_op.drop_index("ix_evidence_items_temporal_status")
        batch_op.drop_index("ix_evidence_items_source_snapshot_id")
        batch_op.drop_constraint("fk_evidence_items_source_snapshot_id", type_="foreignkey")
        batch_op.drop_column("temporal_status")
        batch_op.drop_column("source_snapshot_id")

    op.drop_table("source_snapshots")
    op.drop_table("source_definitions")
