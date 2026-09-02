from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .enums import (
    CompanyResearchRunStatus,
    CompanyResearchTaskStatus,
    DataClassification,
    IdentityCandidateStatus,
    LinkReviewStatus,
    ProfileVersionStatus,
    ReportStatus,
    ResearchCaseStatus,
    ResearchSourceStatus,
    ResolutionStatus,
    RunStatus,
    WorkflowStage,
)
from .ids import new_id


def utc_now() -> datetime:
    return datetime.now(UTC)


claim_evidence = Table(
    "claim_evidence",
    Base.metadata,
    Column("claim_id", ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "evidence_item_id",
        ForeignKey("evidence_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

run_evidence = Table(
    "run_evidence",
    Base.metadata,
    Column("run_id", ForeignKey("workflow_runs.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "evidence_item_id",
        ForeignKey("evidence_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("reporting_cutoff", Date, nullable=True),
    Column("temporal_status", String(40), nullable=True),
    Column("temporal_reason", Text, nullable=True),
    Column("evaluated_at", DateTime(timezone=True), nullable=True),
)

run_source_snapshots = Table(
    "run_source_snapshots",
    Base.metadata,
    Column("run_id", ForeignKey("workflow_runs.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "source_snapshot_id",
        ForeignKey("source_snapshots.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("reporting_cutoff", Date, nullable=False),
    Column("linked_at", DateTime(timezone=True), nullable=False, default=utc_now),
    Index("ix_run_source_snapshots_run_id", "run_id"),
    Index("ix_run_source_snapshots_source_snapshot_id", "source_snapshot_id"),
)

source_snapshot_events = Table(
    "source_snapshot_events",
    Base.metadata,
    Column(
        "source_snapshot_id",
        ForeignKey("source_snapshots.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "company_event_id",
        ForeignKey("company_events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_source_snapshot_events_company_event_id", "company_event_id"),
    Index("ix_source_snapshot_events_source_snapshot_id", "source_snapshot_id"),
)


class CompanyModel(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("co"))
    canonical_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    resolution_status: Mapped[str] = mapped_column(
        String(32), default=ResolutionStatus.RESOLVED.value
    )
    classification: Mapped[str] = mapped_column(
        String(32), default=DataClassification.RESTRICTED.value
    )
    entity_type: Mapped[str | None] = mapped_column(String(32), index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(64), index=True)
    lifecycle_status: Mapped[str | None] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyIdentifierModel(Base):
    __tablename__ = "company_identifiers"
    __table_args__ = (
        UniqueConstraint("scheme", "normalized_value", name="uq_identifier_scheme_value"),
        UniqueConstraint("company_id", "scheme", "normalized_value", name="uq_company_identifier"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("cid"))
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    scheme: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str] = mapped_column(String(255))
    normalized_value: Mapped[str] = mapped_column(String(255), index=True)
    source_key: Mapped[str | None] = mapped_column(String(100))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped[CompanyModel] = relationship()


class IdentityCandidateModel(Base):
    __tablename__ = "identity_candidates"
    __table_args__ = (
        UniqueConstraint(
            "raw_submission_id",
            "imported_company_id",
            "submitted_identifier",
            name="uq_identity_candidate_submission_value",
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ic"))
    raw_submission_id: Mapped[str] = mapped_column(
        ForeignKey("raw_submissions.id", ondelete="CASCADE"), index=True
    )
    imported_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    candidate_company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    submitted_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    identifier_scheme: Mapped[str | None] = mapped_column(String(64))
    submitted_identifier: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32), default=IdentityCandidateStatus.PENDING.value, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class IdentityDecisionModel(Base):
    __tablename__ = "identity_decisions"
    __table_args__ = (UniqueConstraint("candidate_id"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("idn"))
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("identity_candidates.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchTemplateModel(Base):
    __tablename__ = "research_templates"
    __table_args__ = (UniqueConstraint("key"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rt"))
    key: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchTemplateVersionModel(Base):
    __tablename__ = "research_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_research_template_version"),
        UniqueConstraint("sha256"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rtv"))
    template_id: Mapped[str] = mapped_column(
        ForeignKey("research_templates.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(50))
    objective: Mapped[str] = mapped_column(Text)
    required_capabilities_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    optional_capabilities_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    claim_keys_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    budgets_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchCaseModel(Base):
    __tablename__ = "research_cases"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "purpose",
            "template_version_id",
            "classification",
            name="uq_research_case_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("case"))
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    template_version_id: Mapped[str] = mapped_column(
        ForeignKey("research_template_versions.id", ondelete="RESTRICT"), index=True
    )
    purpose: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=ResearchCaseStatus.IDENTITY_HOLD.value, index=True
    )
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped[CompanyModel] = relationship()
    template_version: Mapped[ResearchTemplateVersionModel] = relationship()


class IntakeArtifactModel(Base):
    __tablename__ = "intake_artifacts"
    __table_args__ = (UniqueConstraint("fingerprint"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ia"))
    research_case_id: Mapped[str] = mapped_column(
        ForeignKey("research_cases.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    submitted_value_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    snapshot_path: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    classification: Mapped[str] = mapped_column(String(32), index=True)
    actor: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    research_case: Mapped[ResearchCaseModel] = relationship()
    company: Mapped[CompanyModel] = relationship()


class CompanyDomainModel(Base):
    __tablename__ = "company_domains"
    __table_args__ = (
        UniqueConstraint("company_id", "normalized_domain", name="uq_company_domain"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("dom"))
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    normalized_domain: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=LinkReviewStatus.PENDING.value, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped[CompanyModel] = relationship()


class CompanyDomainDecisionModel(Base):
    __tablename__ = "company_domain_decisions"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("dd"))
    company_domain_id: Mapped[str] = mapped_column(
        ForeignKey("company_domains.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyRelationshipModel(Base):
    __tablename__ = "company_relationships"
    __table_args__ = (
        UniqueConstraint(
            "subject_company_id",
            "related_company_id",
            "relationship_type",
            name="uq_company_relationship_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rel"))
    subject_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    related_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    proposed_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyRelationshipDecisionModel(Base):
    __tablename__ = "company_relationship_decisions"
    __table_args__ = (UniqueConstraint("company_relationship_id"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("reld"))
    company_relationship_id: Mapped[str] = mapped_column(
        ForeignKey("company_relationships.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyIdentifierDecisionModel(Base):
    __tablename__ = "company_identifier_decisions"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("cidr"))
    company_identifier_id: Mapped[str] = mapped_column(
        ForeignKey("company_identifiers.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProfileVersionModel(Base):
    __tablename__ = "profile_versions"
    __table_args__ = (
        UniqueConstraint("research_case_id", "version", name="uq_profile_case_version"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("pv"))
    research_case_id: Mapped[str] = mapped_column(
        ForeignKey("research_cases.id", ondelete="CASCADE"), index=True
    )
    research_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_research_runs.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32), default=ProfileVersionStatus.DRAFT.value, index=True
    )
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(String(255))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    review_reason: Mapped[str | None] = mapped_column(Text)
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    research_case: Mapped[ResearchCaseModel] = relationship()


class CompanyResearchRunModel(Base):
    __tablename__ = "company_research_runs"
    __table_args__ = (UniqueConstraint("request_fingerprint"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("crun"))
    research_case_id: Mapped[str] = mapped_column(
        ForeignKey("research_cases.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    request_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    reporting_cutoff: Mapped[date] = mapped_column(Date, index=True)
    source_policy_version: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(32), default=CompanyResearchRunStatus.PENDING.value, index=True
    )
    budgets_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    usage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    coverage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(255))
    cancelled_by: Mapped[str | None] = mapped_column(String(255))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyResearchTaskModel(Base):
    __tablename__ = "company_research_tasks"
    __table_args__ = (
        UniqueConstraint("research_run_id", "capability", name="uq_company_research_task"),
        UniqueConstraint("request_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ctask"))
    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("company_research_runs.id", ondelete="CASCADE"), index=True
    )
    stage_order: Mapped[int] = mapped_column(Integer)
    capability: Mapped[str] = mapped_column(String(100), index=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=CompanyResearchTaskStatus.PENDING.value, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyResearchTaskAttemptModel(Base):
    __tablename__ = "company_research_task_attempts"
    __table_args__ = (
        UniqueConstraint(
            "research_task_id", "attempt_number", name="uq_company_research_task_attempt"
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("cta"))
    research_task_id: Mapped[str] = mapped_column(
        ForeignKey("company_research_tasks.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str | None] = mapped_column(String(100))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    tool_calls: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyResearchSourceModel(Base):
    __tablename__ = "company_research_sources"
    __table_args__ = (
        UniqueConstraint("research_run_id", "url", name="uq_company_research_source_url"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("crs"))
    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("company_research_runs.id", ondelete="CASCADE"), index=True
    )
    intake_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("intake_artifacts.id", ondelete="RESTRICT"), index=True
    )
    origin: Mapped[str] = mapped_column(String(40), default="public_web", index=True)
    entity_scope: Mapped[str] = mapped_column(String(40), default="legal_entity", index=True)
    url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500))
    publisher_domain: Mapped[str] = mapped_column(String(255), index=True)
    source_tier: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=ResearchSourceStatus.DISCOVERED.value, index=True
    )
    http_status: Mapped[int | None] = mapped_column(Integer)
    media_type: Mapped[str | None] = mapped_column(String(100))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    raw_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    snapshot_path: Mapped[str | None] = mapped_column(Text)
    snapshot_kind: Mapped[str | None] = mapped_column(String(40))
    redaction_count: Mapped[int] = mapped_column(Integer, default=0)
    text_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyResearchClaimModel(Base):
    __tablename__ = "company_research_claims"
    __table_args__ = (UniqueConstraint("claim_hash"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rcl"))
    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("company_research_runs.id", ondelete="CASCADE"), index=True
    )
    research_source_id: Mapped[str] = mapped_column(
        ForeignKey("company_research_sources.id", ondelete="CASCADE"), index=True
    )
    entity_scope: Mapped[str] = mapped_column(String(40), default="legal_entity", index=True)
    claim_hash: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    subject_key: Mapped[str] = mapped_column(String(100), index=True)
    statement: Mapped[str] = mapped_column(Text)
    evidence_span: Mapped[str] = mapped_column(Text)
    source_locator: Mapped[str] = mapped_column(Text)
    event_date: Mapped[str | None] = mapped_column(String(32))
    amount: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str | None] = mapped_column(String(8))
    perspective: Mapped[str] = mapped_column(String(40))
    verification_status: Mapped[str] = mapped_column(String(40), index=True)
    extraction_method: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CatalogueVersionModel(Base):
    __tablename__ = "catalogue_versions"
    __table_args__ = (UniqueConstraint("version"), UniqueConstraint("sha256"))

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("cat"))
    version: Mapped[str] = mapped_column(String(100), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    definition_count: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReportingPeriodModel(Base):
    __tablename__ = "reporting_periods"
    __table_args__ = (UniqueConstraint("label"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rp"))
    label: Mapped[str] = mapped_column(String(100), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MetricDefinitionModel(Base):
    __tablename__ = "metric_definitions"
    __table_args__ = (UniqueConstraint("key"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("md"))
    key: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255))
    data_type: Mapped[str] = mapped_column(String(32))
    sourceability: Mapped[str] = mapped_column(String(32))
    unit: Mapped[str | None] = mapped_column(String(64))
    aliases_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text)
    period_semantics: Mapped[str | None] = mapped_column(String(40), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RawSubmissionModel(Base):
    __tablename__ = "raw_submissions"
    __table_args__ = (
        UniqueConstraint("dataset_id"),
        UniqueConstraint("sha256", "reporting_period_id", name="uq_submission_hash_period"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("raw"))
    dataset_id: Mapped[str] = mapped_column(String(40), index=True)
    reporting_period_id: Mapped[str] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="RESTRICT"), index=True
    )
    source_format: Mapped[str] = mapped_column(String(16))
    original_filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_path: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(32))
    reporting_cutoff: Mapped[date | None] = mapped_column(Date)
    profile_key: Mapped[str | None] = mapped_column(String(100))
    profile_version: Mapped[str | None] = mapped_column(String(50))
    catalogue_version: Mapped[str | None] = mapped_column(String(100))
    catalogue_sha256: Mapped[str | None] = mapped_column(String(64))
    import_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    reporting_period: Mapped[ReportingPeriodModel] = relationship()


class CompanyProgrammeMembershipModel(Base):
    __tablename__ = "company_programme_memberships"
    __table_args__ = (
        UniqueConstraint(
            "raw_submission_id",
            "company_id",
            name="uq_programme_membership_submission_company",
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("pm"))
    raw_submission_id: Mapped[str] = mapped_column(
        ForeignKey("raw_submissions.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    programme_start_date: Mapped[date] = mapped_column(Date, index=True)
    submitted_period_label: Mapped[str] = mapped_column(String(100))
    source_cell: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ObservationModel(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint(
            "raw_submission_id",
            "company_id",
            "metric_definition_id",
            name="uq_observation_submission_company_metric",
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("obs"))
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    metric_definition_id: Mapped[str] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="RESTRICT"), index=True
    )
    reporting_period_id: Mapped[str] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="RESTRICT"), index=True
    )
    raw_submission_id: Mapped[str] = mapped_column(
        ForeignKey("raw_submissions.id", ondelete="RESTRICT"), index=True
    )
    original_value_json: Mapped[Any] = mapped_column(JSON)
    normalized_value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    missing_state: Mapped[str] = mapped_column(String(32), index=True)
    unit: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(3))
    source_cell: Mapped[str | None] = mapped_column(String(32))
    normalization_issue_code: Mapped[str | None] = mapped_column(String(100))
    normalization_issue_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped[CompanyModel] = relationship()
    metric_definition: Mapped[MetricDefinitionModel] = relationship()
    raw_submission: Mapped[RawSubmissionModel] = relationship()


class ObservationNarrativeModel(Base):
    __tablename__ = "observation_narratives"
    __table_args__ = (
        UniqueConstraint(
            "raw_submission_id",
            "company_id",
            "parent_metric_key",
            "source_cell",
            name="uq_observation_narrative_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("nar"))
    observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    raw_submission_id: Mapped[str] = mapped_column(
        ForeignKey("raw_submissions.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    parent_metric_key: Mapped[str] = mapped_column(String(100), index=True)
    body: Mapped[str] = mapped_column(Text)
    source_label: Mapped[str] = mapped_column(String(255))
    source_cell: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvidenceItemModel(Base):
    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ev"))
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    metric_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="SET NULL"), index=True
    )
    raw_submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_submissions.id", ondelete="RESTRICT"), index=True
    )
    source_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="RESTRICT"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(64))
    connector: Mapped[str] = mapped_column(String(100))
    locator: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(255))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    connector_version: Mapped[str] = mapped_column(String(50))
    classification: Mapped[str] = mapped_column(String(32))
    is_untrusted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    temporal_status: Mapped[str | None] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped[CompanyModel | None] = relationship()
    metric_definition: Mapped[MetricDefinitionModel | None] = relationship()


class WorkflowRunModel(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("run"))
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("raw_submissions.dataset_id", ondelete="RESTRICT"), index=True
    )
    reporting_period_id: Mapped[str] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="RESTRICT"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32), default=WorkflowStage.PLAN.value)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reporting_cutoff: Mapped[date | None] = mapped_column(Date)
    evidence_contract_version: Mapped[str | None] = mapped_column(String(100))
    quality_contract_version: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class AgentRunModel(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ar"))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32), index=True)
    role: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExtractionModel(Base):
    __tablename__ = "extractions"
    __table_args__ = (
        UniqueConstraint("run_id", "evidence_item_id", name="uq_extraction_run_evidence"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ext"))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    evidence_item_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    metric_definition_id: Mapped[str] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="RESTRICT"), index=True
    )
    extracted_value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    normalized_value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    missing_state: Mapped[str | None] = mapped_column(String(32), index=True)
    unit: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(3))
    period_label: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(50), default="strict-extraction-v2")
    normalization_issue_code: Mapped[str | None] = mapped_column(String(100))
    evidence_locator: Mapped[str | None] = mapped_column(Text)
    evidence_span: Mapped[str | None] = mapped_column(Text)
    abstain_reason: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 7))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    evidence_item: Mapped[EvidenceItemModel] = relationship()
    metric_definition: Mapped[MetricDefinitionModel] = relationship()


class ReportModel(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("run_id"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rep"))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), index=True
    )
    dataset_id: Mapped[str] = mapped_column(String(40), index=True)
    reporting_period_id: Mapped[str] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default=ReportStatus.DRAFT.value)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sections: Mapped[list[ReportSectionModel]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ReportSectionModel(Base):
    __tablename__ = "report_sections"
    __table_args__ = (
        UniqueConstraint("report_id", "section_key", "version", name="uq_report_section_version"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("sec"))
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    section_key: Mapped[str] = mapped_column(String(100))
    heading: Mapped[str] = mapped_column(String(255))
    order_index: Mapped[int] = mapped_column(Integer)
    body_markdown: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    report: Mapped[ReportModel] = relationship(back_populates="sections")
    claims: Mapped[list[ClaimModel]] = relationship(back_populates="report_section")


class ClaimModel(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("cl"))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    metric_definition_id: Mapped[str] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="RESTRICT"), index=True
    )
    reporting_period_id: Mapped[str] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="RESTRICT"), index=True
    )
    report_section_id: Mapped[str | None] = mapped_column(
        ForeignKey("report_sections.id", ondelete="SET NULL"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    normalized_value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped[CompanyModel] = relationship()
    metric_definition: Mapped[MetricDefinitionModel] = relationship()
    report_section: Mapped[ReportSectionModel | None] = relationship(back_populates="claims")
    evidence_items: Mapped[list[EvidenceItemModel]] = relationship(secondary=claim_evidence)
    verifications: Mapped[list[VerificationModel]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class VerificationModel(Base):
    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ver"))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    rationale: Mapped[str] = mapped_column(Text)
    verifier_role: Mapped[str] = mapped_column(String(100), default="independent_verifier")
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    claim: Mapped[ClaimModel] = relationship(back_populates="verifications")


class ReviewDecisionModel(Base):
    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rev"))
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("report_sections.id", ondelete="SET NULL"), index=True
    )
    actor: Mapped[str] = mapped_column(String(255))
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    report_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceDefinitionModel(Base):
    __tablename__ = "source_definitions"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_source_definition_version"),
        UniqueConstraint("manifest_sha256"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("src"))
    key: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(50))
    publisher: Mapped[str] = mapped_column(String(255))
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    manifest_sha256: Mapped[str] = mapped_column(String(64), index=True)
    admitted: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceSnapshotModel(Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "source_key",
            "request_fingerprint",
            "sha256",
            name="uq_source_snapshot_request_content",
        ),
        Index(
            "ux_source_snapshot_request",
            "source_key",
            "request_fingerprint",
            unique=True,
            sqlite_where=text("status IN ('succeeded', 'no_record')"),
            postgresql_where=text("status IN ('succeeded', 'no_record')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("snap"))
    source_key: Mapped[str] = mapped_column(String(100), index=True)
    source_version: Mapped[str] = mapped_column(String(50))
    request_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    identifier_scheme: Mapped[str] = mapped_column(String(64))
    identifier_value: Mapped[str] = mapped_column(String(255))
    programme_start_date: Mapped[date | None] = mapped_column(Date)
    reporting_cutoff: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    locator: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(100))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    derivation_contract_version: Mapped[str | None] = mapped_column(String(50))
    derivation_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    snapshot_path: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    classification: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvidenceFactModel(Base):
    __tablename__ = "evidence_facts"
    __table_args__ = (
        UniqueConstraint(
            "source_snapshot_id", "fact_key", "source_locator", name="uq_snapshot_fact_locator"
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("fact"))
    source_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    metric_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="SET NULL"), index=True
    )
    fact_key: Mapped[str] = mapped_column(String(100), index=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(3))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_locator: Mapped[str] = mapped_column(Text)
    structured_locator_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(100))
    extraction_schema_version: Mapped[str | None] = mapped_column(String(100))
    temporal_status: Mapped[str | None] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompanyEventModel(Base):
    __tablename__ = "company_events"
    __table_args__ = (UniqueConstraint("event_fingerprint"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("evt"))
    event_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    source_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="SET NULL"), index=True
    )
    raw_submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_submissions.id", ondelete="SET NULL"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    lifecycle_stage: Mapped[str | None] = mapped_column(String(64))
    public_identifier: Mapped[str | None] = mapped_column(String(255), index=True)
    event_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    title: Mapped[str] = mapped_column(String(255))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_locator: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QualityContractModel(Base):
    __tablename__ = "quality_contracts"
    __table_args__ = (UniqueConstraint("version"), UniqueConstraint("sha256"))

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("qc"))
    version: Mapped[str] = mapped_column(String(100), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    rules_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QualityViolationModel(Base):
    __tablename__ = "quality_violations"
    __table_args__ = (UniqueConstraint("fingerprint"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("qv"))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    metric_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="SET NULL"), index=True
    )
    evidence_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("evidence_items.id", ondelete="SET NULL"), index=True
    )
    source_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="SET NULL"), index=True
    )
    rule_key: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(32))
    disposition: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str] = mapped_column(Text)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ExtractionAttemptModel(Base):
    __tablename__ = "extraction_attempts"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "evidence_item_id",
            "attempt_number",
            name="uq_extraction_attempt_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("exa"))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    evidence_item_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True
    )
    extraction_id: Mapped[str | None] = mapped_column(
        ForeignKey("extractions.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    duration_ms: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    escalation_cause: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContextStatisticModel(Base):
    __tablename__ = "context_statistics"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "metric_definition_id", "statistic_key", name="uq_context_statistic"
        ),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("ctx"))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    metric_definition_id: Mapped[str] = mapped_column(
        ForeignKey("metric_definitions.id", ondelete="CASCADE"), index=True
    )
    statistic_key: Mapped[str] = mapped_column(String(100))
    cohort_definition_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    sample_size: Mapped[int] = mapped_column(Integer)
    reporting_cutoff: Mapped[date] = mapped_column(Date)
    source_versions_json: Mapped[dict[str, str]] = mapped_column(JSON)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReportExportModel(Base):
    __tablename__ = "report_exports"
    __table_args__ = (
        UniqueConstraint("report_id", "report_version", name="uq_report_export_version"),
        UniqueConstraint("manifest_sha256"),
    )

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=lambda: new_id("rex"))
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    report_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    artifact_root: Mapped[str] = mapped_column(Text)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    manifest_sha256: Mapped[str] = mapped_column(String(64), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
