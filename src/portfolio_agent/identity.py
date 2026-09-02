"""Reviewed, source-scoped company identity resolution.

Names are search hints, never globally unique identifiers. Only exact identifiers or
named human decisions may merge submitted records into an existing company.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .enums import (
    CompanyLifecycleStatus,
    DataClassification,
    IdentifierScheme,
    IdentityCandidateStatus,
    IdentityDecisionType,
    ResearchCaseStatus,
    ResolutionStatus,
)
from .models import (
    CompanyIdentifierDecisionModel,
    CompanyIdentifierModel,
    CompanyModel,
    CompanyProgrammeMembershipModel,
    IdentityCandidateModel,
    IdentityDecisionModel,
    ObservationModel,
    ObservationNarrativeModel,
    ResearchCaseModel,
    utc_now,
)

_COMPANIES_HOUSE_NUMBER = re.compile(r"(?:[A-Z]{2}\d{6}|\d{8})")


def identifier_source_key(scheme: IdentifierScheme) -> str | None:
    """Return the admitted public-source key bound to an identifier scheme."""

    return {
        IdentifierScheme.COMPANIES_HOUSE_NUMBER: "companies_house",
        IdentifierScheme.UKRI_ORGANISATION_ID: "ukri_gtr",
    }.get(scheme)


def normalize_company_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).casefold().strip()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def normalize_identifier(scheme: IdentifierScheme, value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().upper()
    if scheme is IdentifierScheme.COMPANIES_HOUSE_NUMBER:
        normalized = re.sub(r"[\s-]+", "", normalized)
        if normalized.isdigit() and len(normalized) <= 8:
            normalized = normalized.zfill(8)
    return normalized


def is_valid_companies_house_number(value: str) -> bool:
    return (
        _COMPANIES_HOUSE_NUMBER.fullmatch(
            normalize_identifier(IdentifierScheme.COMPANIES_HOUSE_NUMBER, value)
        )
        is not None
    )


@dataclass(frozen=True, slots=True)
class IdentifierReviewProjection:
    """One derived authority view across legacy candidates and slice decisions."""

    status: IdentityCandidateStatus
    candidates: tuple[IdentityCandidateModel, ...]
    decisions: tuple[IdentityDecisionModel | CompanyIdentifierDecisionModel, ...]


def identity_candidates_for_identifier(
    session: Session,
    identifier: CompanyIdentifierModel,
) -> tuple[IdentityCandidateModel, ...]:
    """Return existing candidate records governed by an exact identifier claim."""

    try:
        scheme = IdentifierScheme(identifier.scheme)
    except ValueError:
        return ()
    candidates = session.scalars(
        select(IdentityCandidateModel).where(
            IdentityCandidateModel.identifier_scheme == identifier.scheme,
            IdentityCandidateModel.imported_company_id == identifier.company_id,
        )
    )
    return tuple(
        candidate
        for candidate in candidates
        if candidate.submitted_identifier is not None
        and normalize_identifier(scheme, candidate.submitted_identifier)
        == identifier.normalized_value
    )


def identifier_review_projection(
    session: Session,
    identifier: CompanyIdentifierModel,
) -> IdentifierReviewProjection:
    """Derive pending/accepted/rejected state without creating a second authority."""

    candidates = identity_candidates_for_identifier(session, identifier)
    candidate_ids = [candidate.id for candidate in candidates]
    legacy_decisions = (
        list(
            session.scalars(
                select(IdentityDecisionModel).where(
                    IdentityDecisionModel.candidate_id.in_(candidate_ids)
                )
            )
        )
        if candidate_ids
        else []
    )
    slice_decisions = list(
        session.scalars(
            select(CompanyIdentifierDecisionModel).where(
                CompanyIdentifierDecisionModel.company_identifier_id == identifier.id
            )
        )
    )
    all_decisions: list[IdentityDecisionModel | CompanyIdentifierDecisionModel] = [
        *legacy_decisions,
        *slice_decisions,
    ]
    decisions = tuple(
        sorted(
            all_decisions,
            key=lambda decision: decision.created_at,
            reverse=True,
        )
    )
    candidate_statuses = {candidate.status for candidate in candidates}
    if IdentityCandidateStatus.PENDING.value in candidate_statuses:
        status = IdentityCandidateStatus.PENDING
    elif IdentityCandidateStatus.ACCEPTED.value in candidate_statuses:
        status = IdentityCandidateStatus.ACCEPTED
    elif candidates:
        status = IdentityCandidateStatus.REJECTED
    elif slice_decisions:
        latest_slice_decision = max(
            slice_decisions,
            key=lambda decision: decision.created_at,
        )
        status = (
            IdentityCandidateStatus.ACCEPTED
            if latest_slice_decision.decision == IdentityDecisionType.ACCEPT.value
            else IdentityCandidateStatus.REJECTED
        )
    else:
        status = (
            IdentityCandidateStatus.ACCEPTED
            if identifier.reviewed
            else IdentityCandidateStatus.PENDING
        )
    return IdentifierReviewProjection(status=status, candidates=candidates, decisions=decisions)


def synchronize_company_identity_review_state(
    session: Session,
    company: CompanyModel,
    *,
    accepted: bool,
) -> None:
    """Keep company and first-slice cases aligned after an exact identity decision."""

    company.resolution_status = (
        ResolutionStatus.RESOLVED.value if accepted else ResolutionStatus.UNRESOLVED.value
    )
    company.lifecycle_status = (
        CompanyLifecycleStatus.ACTIVE.value if accepted else CompanyLifecycleStatus.CANDIDATE.value
    )
    case_status = (
        ResearchCaseStatus.READY.value if accepted else ResearchCaseStatus.IDENTITY_HOLD.value
    )
    for research_case in session.scalars(
        select(ResearchCaseModel).where(ResearchCaseModel.company_id == company.id)
    ):
        research_case.status = case_status
        research_case.updated_at = utc_now()


def synchronize_identifier_review_projection(
    session: Session,
    identifier: CompanyIdentifierModel,
) -> None:
    """Project all candidate decisions into the persisted company/case hold state."""

    projection = identifier_review_projection(session, identifier)
    accepted = projection.status == IdentityCandidateStatus.ACCEPTED
    identifier.reviewed = accepted
    company = session.get(CompanyModel, identifier.company_id)
    if company is None:
        raise ValueError("Identifier company is unavailable.")
    synchronize_company_identity_review_state(session, company, accepted=accepted)


def parse_companies_house_identity(
    value: object,
    *,
    fallback_name: str,
) -> tuple[str, str | None]:
    """Split a workbook identity cell without guessing an invalid number."""

    if value is None or not str(value).strip():
        return fallback_name.strip(), None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    compact_candidates = re.findall(r"\b(?:[A-Za-z]{2}[\s-]?\d{6}|\d{1,8})\b", text)
    valid_number: str | None = None
    matched_text: str | None = None
    for candidate in reversed(compact_candidates):
        if is_valid_companies_house_number(candidate):
            valid_number = normalize_identifier(IdentifierScheme.COMPANIES_HOUSE_NUMBER, candidate)
            matched_text = candidate
            break
    if valid_number is None:
        return text, None
    assert matched_text is not None
    official_name = text.replace(matched_text, " ")
    official_name = re.sub(r"[\s,;:()\[\]-]+", " ", official_name).strip()
    return official_name or fallback_name.strip(), valid_number


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    company: CompanyModel | None
    issue_code: str | None = None
    issue_message: str | None = None
    candidate_id: str | None = None


def _new_company(
    session: Session,
    *,
    name: str,
    classification: DataClassification,
    status: ResolutionStatus,
) -> CompanyModel:
    company = CompanyModel(
        canonical_name=name.strip(),
        normalized_name=normalize_company_name(name),
        external_id=None,
        classification=classification.value,
        resolution_status=status.value,
    )
    session.add(company)
    session.flush()
    return company


def _candidate(
    session: Session,
    *,
    raw_submission_id: str,
    imported_company: CompanyModel,
    suggested_company: CompanyModel | None,
    name: str,
    scheme: IdentifierScheme | None,
    identifier: str | None,
    reason_code: str,
) -> IdentityCandidateModel:
    candidate = IdentityCandidateModel(
        raw_submission_id=raw_submission_id,
        imported_company_id=imported_company.id,
        candidate_company_id=suggested_company.id if suggested_company else None,
        submitted_name=name.strip(),
        normalized_name=normalize_company_name(name),
        identifier_scheme=scheme.value if scheme else None,
        submitted_identifier=identifier,
        status=IdentityCandidateStatus.PENDING.value,
        reason_code=reason_code,
    )
    session.add(candidate)
    session.flush()
    return candidate


def resolve_company_identity(
    session: Session,
    *,
    raw_submission_id: str,
    name: str,
    external_id: str | None,
    identifier_scheme: IdentifierScheme,
    classification: DataClassification,
) -> IdentityResolution:
    clean_name = name.strip()
    normalized_name = normalize_company_name(clean_name)
    if not normalized_name:
        return IdentityResolution(
            None,
            "missing_company_name",
            "Company row has no usable identity and was skipped.",
        )

    same_name = list(
        session.scalars(
            select(CompanyModel).where(CompanyModel.normalized_name == normalized_name)
        ).all()
    )
    clean_identifier = external_id.strip() if external_id else None
    if clean_identifier is None:
        imported = _new_company(
            session,
            name=clean_name,
            classification=classification,
            status=ResolutionStatus.UNRESOLVED,
        )
        suggested = same_name[0] if len(same_name) == 1 else None
        candidate = _candidate(
            session,
            raw_submission_id=raw_submission_id,
            imported_company=imported,
            suggested_company=suggested,
            name=clean_name,
            scheme=None,
            identifier=None,
            reason_code="name_only_requires_review",
        )
        return IdentityResolution(
            imported,
            "identity_review_required",
            "Name-only identity was imported into an unresolved company pending human review.",
            candidate.id,
        )

    normalized_identifier = normalize_identifier(identifier_scheme, clean_identifier)
    if (
        identifier_scheme is IdentifierScheme.COMPANIES_HOUSE_NUMBER
        and not is_valid_companies_house_number(normalized_identifier)
    ):
        imported = _new_company(
            session,
            name=clean_name,
            classification=classification,
            status=ResolutionStatus.UNRESOLVED,
        )
        candidate = _candidate(
            session,
            raw_submission_id=raw_submission_id,
            imported_company=imported,
            suggested_company=same_name[0] if len(same_name) == 1 else None,
            name=clean_name,
            scheme=identifier_scheme,
            identifier=clean_identifier,
            reason_code="invalid_companies_house_number",
        )
        return IdentityResolution(
            imported,
            "invalid_company_identifier",
            "The submitted Companies House number failed the structural validation rule.",
            candidate.id,
        )

    exact_identifier = session.scalar(
        select(CompanyIdentifierModel).where(
            CompanyIdentifierModel.scheme == identifier_scheme.value,
            CompanyIdentifierModel.normalized_value == normalized_identifier,
        )
    )
    if exact_identifier is not None:
        company = session.get(CompanyModel, exact_identifier.company_id)
        assert company is not None
        if company.classification != classification.value:
            return IdentityResolution(
                None,
                "classification_conflict",
                "Exact identifier belongs to a company under a different data classification.",
            )
        if company.normalized_name != normalized_name:
            imported = _new_company(
                session,
                name=clean_name,
                classification=classification,
                status=ResolutionStatus.UNRESOLVED,
            )
            candidate = _candidate(
                session,
                raw_submission_id=raw_submission_id,
                imported_company=imported,
                suggested_company=company,
                name=clean_name,
                scheme=identifier_scheme,
                identifier=normalized_identifier,
                reason_code="identifier_name_conflict",
            )
            return IdentityResolution(
                imported,
                "identity_review_required",
                "Exact identifier and submitted name disagree; no automatic merge was made.",
                candidate.id,
            )
        if not exact_identifier.reviewed or (
            identifier_scheme is not IdentifierScheme.LEGACY
            and company.resolution_status != ResolutionStatus.RESOLVED.value
        ):
            company.resolution_status = ResolutionStatus.UNRESOLVED.value
            candidate = _candidate(
                session,
                raw_submission_id=raw_submission_id,
                imported_company=company,
                suggested_company=company,
                name=clean_name,
                scheme=identifier_scheme,
                identifier=normalized_identifier,
                reason_code="identifier_requires_review",
            )
            return IdentityResolution(
                company,
                "identity_review_required",
                "Exact public identifier is structurally valid but requires named human review.",
                candidate.id,
            )
        return IdentityResolution(company)

    conflicting_same_name: CompanyModel | None = None
    for company in same_name:
        company_identifiers = list(
            session.scalars(
                select(CompanyIdentifierModel).where(
                    CompanyIdentifierModel.company_id == company.id,
                    CompanyIdentifierModel.scheme == identifier_scheme.value,
                )
            ).all()
        )
        if company_identifiers:
            conflicting_same_name = company
            break
    if conflicting_same_name is not None:
        imported = _new_company(
            session,
            name=clean_name,
            classification=classification,
            status=ResolutionStatus.UNRESOLVED,
        )
        candidate = _candidate(
            session,
            raw_submission_id=raw_submission_id,
            imported_company=imported,
            suggested_company=conflicting_same_name,
            name=clean_name,
            scheme=identifier_scheme,
            identifier=normalized_identifier,
            reason_code="name_identifier_collision",
        )
        return IdentityResolution(
            imported,
            "ambiguous_company_identity",
            "Exact company name maps to a different source-scoped identifier.",
            candidate.id,
        )

    requires_review = identifier_scheme is not IdentifierScheme.LEGACY
    company = _new_company(
        session,
        name=clean_name,
        classification=classification,
        status=(ResolutionStatus.UNRESOLVED if requires_review else ResolutionStatus.RESOLVED),
    )
    company.external_id = clean_identifier
    session.add(
        CompanyIdentifierModel(
            company_id=company.id,
            scheme=identifier_scheme.value,
            value=clean_identifier,
            normalized_value=normalized_identifier,
            source_key=identifier_source_key(identifier_scheme),
            reviewed=not requires_review,
        )
    )
    session.flush()
    if requires_review:
        candidate = _candidate(
            session,
            raw_submission_id=raw_submission_id,
            imported_company=company,
            suggested_company=company,
            name=clean_name,
            scheme=identifier_scheme,
            identifier=normalized_identifier,
            reason_code="identifier_requires_review",
        )
        return IdentityResolution(
            company,
            "identity_review_required",
            "Exact public identifier is structurally valid but requires named human review.",
            candidate.id,
        )
    return IdentityResolution(company)


def decide_identity_candidate(
    session: Session,
    *,
    candidate_id: str,
    decision: IdentityDecisionType,
    actor: str,
    reason: str,
    company_id: str | None = None,
) -> IdentityDecisionModel:
    clean_actor = actor.strip()
    clean_reason = reason.strip()
    if len(clean_actor) < 2 or len(clean_reason) < 5:
        raise ValueError("Identity decisions require a named actor and substantive reason.")
    candidate = session.get(IdentityCandidateModel, candidate_id)
    if candidate is None:
        raise ValueError("Unknown identity candidate.")
    if candidate.status != IdentityCandidateStatus.PENDING.value:
        raise ValueError("Identity candidate already has a final decision.")

    target: CompanyModel | None = None
    affected_identifier: CompanyIdentifierModel | None = None
    if decision is IdentityDecisionType.ACCEPT:
        target_id = company_id or candidate.candidate_company_id or candidate.imported_company_id
        target = session.get(CompanyModel, target_id)
        imported = session.get(CompanyModel, candidate.imported_company_id)
        if target is None or imported is None:
            raise ValueError("Accepted identity target is unavailable.")
        if target.classification != imported.classification:
            raise ValueError("Identity merge cannot cross data-classification boundaries.")
        if target.id != imported.id:
            session.execute(
                update(ObservationModel)
                .where(
                    ObservationModel.raw_submission_id == candidate.raw_submission_id,
                    ObservationModel.company_id == imported.id,
                )
                .values(company_id=target.id)
            )
            session.execute(
                update(ObservationNarrativeModel)
                .where(
                    ObservationNarrativeModel.raw_submission_id == candidate.raw_submission_id,
                    ObservationNarrativeModel.company_id == imported.id,
                )
                .values(company_id=target.id)
            )
            session.execute(
                update(CompanyProgrammeMembershipModel)
                .where(
                    CompanyProgrammeMembershipModel.raw_submission_id
                    == candidate.raw_submission_id,
                    CompanyProgrammeMembershipModel.company_id == imported.id,
                )
                .values(company_id=target.id)
            )
        target.resolution_status = ResolutionStatus.RESOLVED.value
        if candidate.identifier_scheme and candidate.submitted_identifier:
            scheme = IdentifierScheme(candidate.identifier_scheme)
            normalized = normalize_identifier(scheme, candidate.submitted_identifier)
            existing = session.scalar(
                select(CompanyIdentifierModel).where(
                    CompanyIdentifierModel.scheme == scheme.value,
                    CompanyIdentifierModel.normalized_value == normalized,
                )
            )
            if existing is not None and existing.company_id != target.id:
                raise ValueError("Identifier is already attached to a different company.")
            if existing is None:
                existing = CompanyIdentifierModel(
                    company_id=target.id,
                    scheme=scheme.value,
                    value=candidate.submitted_identifier,
                    normalized_value=normalized,
                    source_key=identifier_source_key(scheme),
                    reviewed=True,
                )
                session.add(existing)
            else:
                existing.reviewed = True
                existing.source_key = identifier_source_key(scheme)
            affected_identifier = existing
            target.external_id = candidate.submitted_identifier
        candidate.status = IdentityCandidateStatus.ACCEPTED.value
    else:
        candidate.status = IdentityCandidateStatus.REJECTED.value
        if candidate.identifier_scheme and candidate.submitted_identifier:
            scheme = IdentifierScheme(candidate.identifier_scheme)
            normalized = normalize_identifier(scheme, candidate.submitted_identifier)
            existing = session.scalar(
                select(CompanyIdentifierModel).where(
                    CompanyIdentifierModel.scheme == scheme.value,
                    CompanyIdentifierModel.normalized_value == normalized,
                )
            )
            if existing is not None and existing.company_id == candidate.imported_company_id:
                affected_identifier = existing

    if affected_identifier is not None:
        synchronize_identifier_review_projection(session, affected_identifier)

    record = IdentityDecisionModel(
        candidate_id=candidate.id,
        company_id=target.id if target else company_id,
        decision=decision.value,
        actor=clean_actor,
        reason=clean_reason,
    )
    session.add(record)
    session.flush()
    return record
