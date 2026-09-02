"""Add run-relative evidence and canonical snapshot-event associations.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_evidence") as batch_op:
        batch_op.add_column(sa.Column("reporting_cutoff", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("temporal_status", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("temporal_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE run_evidence SET "
            "reporting_cutoff = (SELECT reporting_cutoff FROM workflow_runs "
            "WHERE workflow_runs.id = run_evidence.run_id), "
            "temporal_status = COALESCE((SELECT temporal_status FROM evidence_items "
            "WHERE evidence_items.id = run_evidence.evidence_item_id), "
            "CASE WHEN (SELECT source_type FROM evidence_items "
            "WHERE evidence_items.id = run_evidence.evidence_item_id) = 'portfolio_submission' "
            "THEN 'eligible' ELSE 'missing_published_at' END), "
            "temporal_reason = 'Migrated legacy decision; new runs re-evaluate at their cutoff', "
            "evaluated_at = CURRENT_TIMESTAMP"
        )
    )

    op.create_table(
        "run_source_snapshots",
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=48), nullable=False),
        sa.Column("reporting_cutoff", sa.Date(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", "source_snapshot_id"),
    )
    op.create_index("ix_run_source_snapshots_run_id", "run_source_snapshots", ["run_id"])
    op.create_index(
        "ix_run_source_snapshots_source_snapshot_id",
        "run_source_snapshots",
        ["source_snapshot_id"],
    )
    connection.execute(
        sa.text(
            "INSERT INTO run_source_snapshots "
            "(run_id, source_snapshot_id, reporting_cutoff, linked_at) "
            "SELECT DISTINCT re.run_id, ei.source_snapshot_id, wr.reporting_cutoff, "
            "CURRENT_TIMESTAMP FROM run_evidence re "
            "JOIN evidence_items ei ON ei.id = re.evidence_item_id "
            "JOIN workflow_runs wr ON wr.id = re.run_id "
            "WHERE ei.source_snapshot_id IS NOT NULL AND wr.reporting_cutoff IS NOT NULL"
        )
    )

    op.create_table(
        "source_snapshot_events",
        sa.Column("source_snapshot_id", sa.String(length=48), nullable=False),
        sa.Column("company_event_id", sa.String(length=48), nullable=False),
        sa.ForeignKeyConstraint(["company_event_id"], ["company_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("source_snapshot_id", "company_event_id"),
    )
    op.create_index(
        "ix_source_snapshot_events_company_event_id",
        "source_snapshot_events",
        ["company_event_id"],
    )
    op.create_index(
        "ix_source_snapshot_events_source_snapshot_id",
        "source_snapshot_events",
        ["source_snapshot_id"],
    )
    connection.execute(
        sa.text(
            "INSERT INTO source_snapshot_events (source_snapshot_id, company_event_id) "
            "SELECT source_snapshot_id, id FROM company_events "
            "WHERE source_snapshot_id IS NOT NULL"
        )
    )

    op.create_index(
        "ux_source_snapshot_request",
        "source_snapshots",
        ["source_key", "request_fingerprint"],
        unique=True,
        sqlite_where=sa.text("status IN ('succeeded', 'no_record')"),
        postgresql_where=sa.text("status IN ('succeeded', 'no_record')"),
    )


def downgrade() -> None:
    op.drop_index("ux_source_snapshot_request", table_name="source_snapshots")
    op.drop_table("source_snapshot_events")
    op.drop_table("run_source_snapshots")
    with op.batch_alter_table("run_evidence") as batch_op:
        batch_op.drop_column("evaluated_at")
        batch_op.drop_column("temporal_reason")
        batch_op.drop_column("temporal_status")
        batch_op.drop_column("reporting_cutoff")
