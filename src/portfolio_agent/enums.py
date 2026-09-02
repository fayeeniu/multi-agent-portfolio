from enum import StrEnum


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    SYNTHETIC = "synthetic"


class Sourceability(StrEnum):
    PUBLICLY_SOURCEABLE = "publicly_sourceable"
    INTERNAL_ONLY = "internal_only"
    MIXED = "mixed"
    DERIVED = "derived"


class MetricDataType(StrEnum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    BOOLEAN = "boolean"
    TEXT = "text"
    DATE = "date"
    DURATION_HOURS = "duration_hours"


class MissingState(StrEnum):
    OBSERVED = "observed"
    BLANK = "blank"
    ZERO = "zero"
    NONE_STATED = "none_stated"
    NOT_APPLICABLE = "not_applicable"
    NOT_REPORTED = "not_reported"
    NOT_FOUND_PUBLICLY = "not_found_publicly"
    FILING_NOT_DUE = "filing_not_due"
    DORMANT = "dormant"
    NOT_REQUIRED = "not_required"
    SOURCE_UNAVAILABLE = "source_unavailable"
    INVALID = "invalid"


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class CompanyEntityType(StrEnum):
    REGISTERED = "registered"
    UNINCORPORATED = "unincorporated"
    UNKNOWN = "unknown"


class CompanyLifecycleStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ResearchCaseStatus(StrEnum):
    IDENTITY_HOLD = "identity_hold"
    READY = "ready"
    ARCHIVED = "archived"


class IntakeArtifactKind(StrEnum):
    COMPANIES_HOUSE_NUMBER = "companies_house_number"
    WEBSITE = "website"
    DOCUMENT = "document"
    NAME_JURISDICTION = "name_jurisdiction"
    BULK_ROW = "bulk_row"


class LinkReviewStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class EvidenceScope(StrEnum):
    LEGAL_ENTITY = "legal_entity"
    CONSOLIDATED_GROUP = "consolidated_group"


class CompanyRelationshipType(StrEnum):
    CONSOLIDATED_GROUP = "consolidated_group"


class ProfileVersionStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class CompanyResearchRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CompanyResearchTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchSourceStatus(StrEnum):
    DISCOVERED = "discovered"
    FETCHED = "fetched"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ResearchClaimCategory(StrEnum):
    IDENTITY = "identity"
    FUNDING = "funding"
    AWARDS = "awards"
    CORPORATE_ACTIONS = "corporate_actions"
    PERFORMANCE = "performance"
    CHALLENGES = "challenges"
    PRODUCTS_MARKET = "products_market"
    PUBLIC_DISCOURSE = "public_discourse"
    REGULATION = "regulation"
    TECHNOLOGY = "technology"
    OTHER = "other"


class IdentifierScheme(StrEnum):
    COMPANIES_HOUSE_NUMBER = "companies_house_number"
    UKRI_ORGANISATION_ID = "ukri_organisation_id"
    LEGACY = "legacy"
    REVIEWED_ALIAS = "reviewed_alias"


class IdentityCandidateStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class IdentityDecisionType(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class TemporalEligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    FUTURE_PUBLISHED = "future_published"
    FUTURE_EFFECTIVE = "future_effective"
    EXPIRED = "expired"
    MISSING_PUBLISHED_AT = "missing_published_at"
    NOT_APPLICABLE = "not_applicable"


class QualityDisposition(StrEnum):
    PASS = "pass"
    WARN = "warn"
    HOLD = "hold"
    EXCLUDE = "exclude"


class CollectionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    NO_RECORD = "no_record"
    SOURCE_UNAVAILABLE = "source_unavailable"
    FAILED = "failed"


class ExtractionAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    ABSTAINED = "abstained"
    REJECTED = "rejected"
    FAILED = "failed"


class EventType(StrEnum):
    INCORPORATED = "incorporated"
    DISSOLVED = "dissolved"
    STATUS_CHANGED = "status_changed"
    ACCOUNTS_FILED = "accounts_filed"
    CHARGE_REGISTERED = "charge_registered"
    SHARE_EVENT = "share_event"
    UKRI_OPPORTUNITY = "ukri_opportunity"
    UKRI_DECISION = "ukri_decision"
    UKRI_AWARD = "ukri_award"
    UKRI_PROJECT = "ukri_project"
    UKRI_OUTCOME = "ukri_outcome"
    PRIVATE_FUNDING_REPORTED = "private_funding_reported"


class WorkflowStage(StrEnum):
    PLAN = "plan"
    RESOLVE = "resolve"
    COLLECT = "collect"
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    VERIFY = "verify"
    COMPOSE = "compose"
    HUMAN_REVIEW = "human_review"
    APPROVE_EXPORT = "approve_export"
    COMPLETE = "complete"
    FAILED = "failed"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerificationStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    STALE = "stale"
    REJECTED_UNTRUSTED = "rejected_untrusted"


class ReportStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    EXPORTING = "exporting"
    REJECTED = "rejected"
    EXPORTED = "exported"


class ReviewDecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_EDIT = "request_edit"


class EvaluationCondition(StrEnum):
    MANUAL = "manual"
    DETERMINISTIC_SINGLE_AGENT = "deterministic_single_agent"
    MULTI_AGENT_VERIFICATION = "multi_agent_verification"
    MULTI_AGENT_HITL = "multi_agent_hitl"
