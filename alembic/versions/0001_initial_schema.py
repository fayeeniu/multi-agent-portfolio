"""Create the initial evidence-first portfolio schema.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[str]:
    return sa.Column("id", sa.String(length=48), nullable=False)


def _created_at() -> sa.Column[datetime]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "companies",
        _id(),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("resolution_status", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name"),
    )
    op.create_index("ix_companies_external_id", "companies", ["external_id"])
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"])

    op.create_table(
        "metric_definitions",
        _id(),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("sourceability", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("aliases_json", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_metric_definitions_key", "metric_definitions", ["key"])

    op.create_table(
        "reporting_periods",
        _id(),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_index("ix_reporting_periods_label", "reporting_periods", ["label"])

    op.create_table(
        "raw_submissions",
        _id(),
        sa.Column("dataset_id", sa.String(length=40), nullable=False),
        sa.Column("reporting_period_id", sa.String(length=48), nullable=False),
        sa.Column("source_format", sa.String(length=16), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("snapshot_path", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["reporting_period_id"], ["reporting_periods.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id"),
        sa.UniqueConstraint("sha256", "reporting_period_id", name="uq_submission_hash_period"),
    )
    op.create_index("ix_raw_submissions_dataset_id", "raw_submissions", ["dataset_id"])
    op.create_index(
        "ix_raw_submissions_reporting_period_id", "raw_submissions", ["reporting_period_id"]
    )
    op.create_index("ix_raw_submissions_sha256", "raw_submissions", ["sha256"])

    op.create_table(
        "evidence_items",
        _id(),
        sa.Column("company_id", sa.String(length=48), nullable=True),
        sa.Column("metric_definition_id", sa.String(length=48), nullable=True),
        sa.Column("raw_submission_id", sa.String(length=48), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("connector", sa.String(length=100), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("connector_version", sa.String(length=50), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("is_untrusted", sa.Boolean(), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"], ["metric_definitions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["raw_submission_id"], ["raw_submissions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_items_checksum", "evidence_items", ["checksum"])
    op.create_index("ix_evidence_items_company_id", "evidence_items", ["company_id"])
    op.create_index(
        "ix_evidence_items_metric_definition_id",
        "evidence_items",
        ["metric_definition_id"],
    )
    op.create_index("ix_evidence_items_raw_submission_id", "evidence_items", ["raw_submission_id"])

    op.create_table(
        "observations",
        _id(),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("metric_definition_id", sa.String(length=48), nullable=False),
        sa.Column("reporting_period_id", sa.String(length=48), nullable=False),
        sa.Column("raw_submission_id", sa.String(length=48), nullable=False),
        sa.Column("original_value_json", sa.JSON(), nullable=False),
        sa.Column("normalized_value_json", sa.JSON(), nullable=True),
        sa.Column("missing_state", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("source_cell", sa.String(length=32), nullable=True),
        sa.Column("normalization_issue_code", sa.String(length=100), nullable=True),
        sa.Column("normalization_issue_message", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"], ["metric_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reporting_period_id"], ["reporting_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["raw_submission_id"], ["raw_submissions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "raw_submission_id",
            "company_id",
            "metric_definition_id",
            name="uq_observation_submission_company_metric",
        ),
    )
    op.create_index("ix_observations_company_id", "observations", ["company_id"])
    op.create_index(
        "ix_observations_metric_definition_id", "observations", ["metric_definition_id"]
    )
    op.create_index("ix_observations_missing_state", "observations", ["missing_state"])
    op.create_index("ix_observations_raw_submission_id", "observations", ["raw_submission_id"])
    op.create_index("ix_observations_reporting_period_id", "observations", ["reporting_period_id"])

    op.create_table(
        "workflow_runs",
        _id(),
        sa.Column("dataset_id", sa.String(length=40), nullable=False),
        sa.Column("reporting_period_id", sa.String(length=48), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["raw_submissions.dataset_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reporting_period_id"], ["reporting_periods.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_runs_dataset_id", "workflow_runs", ["dataset_id"])
    op.create_index(
        "ix_workflow_runs_reporting_period_id", "workflow_runs", ["reporting_period_id"]
    )

    op.create_table(
        "agent_runs",
        _id(),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_run_id", "agent_runs", ["run_id"])
    op.create_index("ix_agent_runs_stage", "agent_runs", ["stage"])

    op.create_table(
        "extractions",
        _id(),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("evidence_item_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("metric_definition_id", sa.String(length=48), nullable=False),
        sa.Column("extracted_value_json", sa.JSON(), nullable=True),
        sa.Column("normalized_value_json", sa.JSON(), nullable=True),
        sa.Column("missing_state", sa.String(length=32), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("period_label", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("normalization_issue_code", sa.String(length=100), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"], ["metric_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "evidence_item_id", name="uq_extraction_run_evidence"),
    )
    op.create_index("ix_extractions_company_id", "extractions", ["company_id"])
    op.create_index("ix_extractions_evidence_item_id", "extractions", ["evidence_item_id"])
    op.create_index("ix_extractions_metric_definition_id", "extractions", ["metric_definition_id"])
    op.create_index("ix_extractions_missing_state", "extractions", ["missing_state"])
    op.create_index("ix_extractions_run_id", "extractions", ["run_id"])

    op.create_table(
        "reports",
        _id(),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("dataset_id", sa.String(length=40), nullable=False),
        sa.Column("reporting_period_id", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["reporting_period_id"], ["reporting_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_reports_dataset_id", "reports", ["dataset_id"])
    op.create_index("ix_reports_reporting_period_id", "reports", ["reporting_period_id"])
    op.create_index("ix_reports_run_id", "reports", ["run_id"])

    op.create_table(
        "run_evidence",
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("evidence_item_id", sa.String(length=48), nullable=False),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "evidence_item_id"),
    )

    op.create_table(
        "report_sections",
        _id(),
        sa.Column("report_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=True),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id", "section_key", "version", name="uq_report_section_version"
        ),
    )
    op.create_index("ix_report_sections_company_id", "report_sections", ["company_id"])
    op.create_index("ix_report_sections_report_id", "report_sections", ["report_id"])

    op.create_table(
        "claims",
        _id(),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("company_id", sa.String(length=48), nullable=False),
        sa.Column("metric_definition_id", sa.String(length=48), nullable=False),
        sa.Column("reporting_period_id", sa.String(length=48), nullable=False),
        sa.Column("report_section_id", sa.String(length=48), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_value_json", sa.JSON(), nullable=True),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"], ["metric_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["report_section_id"], ["report_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["reporting_period_id"], ["reporting_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_company_id", "claims", ["company_id"])
    op.create_index("ix_claims_metric_definition_id", "claims", ["metric_definition_id"])
    op.create_index("ix_claims_report_section_id", "claims", ["report_section_id"])
    op.create_index("ix_claims_reporting_period_id", "claims", ["reporting_period_id"])
    op.create_index("ix_claims_run_id", "claims", ["run_id"])
    op.create_index("ix_claims_verification_status", "claims", ["verification_status"])

    op.create_table(
        "review_decisions",
        _id(),
        sa.Column("report_id", sa.String(length=48), nullable=False),
        sa.Column("section_id", sa.String(length=48), nullable=True),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["report_sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_decisions_report_id", "review_decisions", ["report_id"])
    op.create_index("ix_review_decisions_section_id", "review_decisions", ["section_id"])

    op.create_table(
        "claim_evidence",
        sa.Column("claim_id", sa.String(length=48), nullable=False),
        sa.Column("evidence_item_id", sa.String(length=48), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("claim_id", "evidence_item_id"),
    )

    op.create_table(
        "verifications",
        _id(),
        sa.Column("claim_id", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("verifier_role", sa.String(length=100), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verifications_claim_id", "verifications", ["claim_id"])
    op.create_index("ix_verifications_status", "verifications", ["status"])


def downgrade() -> None:
    op.drop_table("verifications")
    op.drop_table("claim_evidence")
    op.drop_table("review_decisions")
    op.drop_table("claims")
    op.drop_table("report_sections")
    op.drop_table("run_evidence")
    op.drop_table("reports")
    op.drop_table("extractions")
    op.drop_table("agent_runs")
    op.drop_table("workflow_runs")
    op.drop_table("observations")
    op.drop_table("evidence_items")
    op.drop_table("raw_submissions")
    op.drop_table("reporting_periods")
    op.drop_table("metric_definitions")
    op.drop_table("companies")
