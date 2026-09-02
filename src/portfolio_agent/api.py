"""JSON projection layer for the Next.js agent control room.

This module adds no business logic. It projects persisted records into stable
JSON view models for the frontend. Every status, hash, count, and timing value
shown to a user originates from a persisted row; nothing here guesses or smooths
over a missing value.
"""

from __future__ import annotations

import hmac
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .bootstrap import Runtime
from .company_intelligence import (
    MAX_DOCUMENTS_PER_BATCH,
    CompanyDocumentUpload,
    CompanyIntakeRequest,
    CompanyIntakeValidationError,
)
from .company_research import (
    REASONING_CAPABILITIES,
    TASKS,
    CompanyResearchError,
    route_for,
    validated_profile_content,
)
from .config import COMPANY_RESEARCH_REPAIR_EFFORT, COMPANY_RESEARCH_SELECTION_EFFORT
from .enums import (
    CompanyResearchRunStatus,
    CompanyResearchTaskStatus,
    DataClassification,
    EvidenceScope,
    IdentityCandidateStatus,
    IdentityDecisionType,
    ProfileVersionStatus,
    ResearchClaimCategory,
    ResearchSourceStatus,
)
from .identity import identifier_review_projection
from .investment_metrics import build_investment_report
from .models import (
    CompanyDomainModel,
    CompanyIdentifierModel,
    CompanyModel,
    CompanyRelationshipModel,
    CompanyResearchClaimModel,
    CompanyResearchRunModel,
    CompanyResearchSourceModel,
    CompanyResearchTaskAttemptModel,
    CompanyResearchTaskModel,
    IntakeArtifactModel,
    ProfileVersionModel,
    ResearchCaseModel,
)

JsonDict = dict[str, Any]


def humanize(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()

#: Bounded roles that actually execute inside a company research run. The
#: capability keys match :data:`portfolio_agent.company_research.TASKS`; the gate
#: keys are human or identity checkpoints that the orchestrator will not cross on
#: its own. Descriptions restate the enforced contract, not an aspiration.
AGENT_ROLES: tuple[JsonDict, ...] = (
    {
        "key": "identity",
        "label": "Legal entity resolver",
        "layer": "Identity",
        "engine": "human",
        "summary": "Binds the case to one exact Companies House number under a named decision.",
        "owns": "Exact identifiers, reviewed aliases and verified first-party domains.",
        "must_not": "Merge on a name, a filename or a domain that no reviewer has accepted.",
        "inputs": "Submitted identifier claim and reviewer rationale.",
        "outputs": "Accepted or rejected identifier; the case stays held until accepted.",
    },
    {
        "key": "discover_sources",
        "label": "Source planner",
        "layer": "Planning",
        "engine": "model",
        "summary": "Asks the external model, with a bounded web-search tool, for candidate "
        "public source URLs. It records URLs only — never facts.",
        "owns": "The candidate source set for this run, capped by the pinned source budget.",
        "must_not": "Invent identifiers or parse page content into claims.",
        "inputs": "Company number, canonical name, reporting cutoff, pinned budgets.",
        "outputs": "Discovered source rows with publisher domain and source tier.",
    },
    {
        "key": "capture_sources",
        "label": "Safe public fetcher",
        "layer": "Acquisition",
        "engine": "deterministic",
        "summary": "Fetches each candidate over a DNS-pinned, robots-aware, byte-capped "
        "transport, redacts personal contact patterns, and writes an immutable snapshot.",
        "owns": "Raw bytes, SHA-256 checksums, HTTP status and per-source terminal state.",
        "must_not": "Follow instructions found in a page, or store an unredacted snapshot.",
        "inputs": "Discovered source URLs and the run's pinned transport budgets.",
        "outputs": "Fetched, blocked, unsupported or failed state for every candidate.",
    },
    {
        "key": "extract_claims",
        "label": "Claim extractor and span validator",
        "layer": "Extraction",
        "engine": "model",
        "summary": "The model proposes claims against a strict schema; deterministic code then "
        "admits only claims whose statement is a verbatim span of the captured snapshot.",
        "owns": "Admitted claims, their exact evidence span and their source locator.",
        "must_not": "Admit a paraphrase, a post-cutoff event, personal contact data, an "
        "injection pattern or a recommendation.",
        "inputs": "Redacted snapshot text, checksum-verified against the stored bytes.",
        "outputs": "Claims carrying category, perspective, span and source linkage.",
    },
    {
        "key": "compose_deck",
        "label": "Profile composer",
        "layer": "Synthesis",
        "engine": "deterministic",
        "summary": "Groups admitted claims into profile sections, raises a contradiction when "
        "one subject carries different statements from different sources, and hashes the result.",
        "owns": "The versioned company profile, its coverage counts and its contradiction ledger.",
        "must_not": "Add a sentence that is not an admitted claim, or resolve a contradiction.",
        "inputs": "Admitted claims and captured source records for this run only.",
        "outputs": "One pending-review profile version with a content checksum.",
    },
    {
        "key": "human_review",
        "label": "Named reviewer",
        "layer": "Human",
        "engine": "human",
        "summary": "The only role that can approve. Approval records review of one profile "
        "version; it does not upgrade held or contradicted evidence.",
        "owns": "Approve and reject authority.",
        "must_not": "Alter immutable evidence or a recorded verification outcome.",
        "inputs": "The pending profile version and its expected lock version.",
        "outputs": "An audited approval or rejection with a written rationale.",
    },
)

_ROLE_BY_KEY: dict[str, JsonDict] = {role["key"]: role for role in AGENT_ROLES}

_CLAIM_CATEGORY_LABELS: dict[str, str] = {
    ResearchClaimCategory.IDENTITY.value: "Identity and status",
    ResearchClaimCategory.FUNDING.value: "Funding and capital",
    ResearchClaimCategory.AWARDS.value: "Grants and awards",
    ResearchClaimCategory.CORPORATE_ACTIONS.value: "Corporate actions",
    ResearchClaimCategory.PERFORMANCE.value: "Reported performance",
    ResearchClaimCategory.CHALLENGES.value: "Challenges and risks",
    ResearchClaimCategory.PRODUCTS_MARKET.value: "Products and market",
    ResearchClaimCategory.PUBLIC_DISCOURSE.value: "Public discourse",
    ResearchClaimCategory.REGULATION.value: "Regulation",
    ResearchClaimCategory.TECHNOLOGY.value: "Technology",
    ResearchClaimCategory.OTHER.value: "Other evidence",
}

_PERSPECTIVE_LABELS: dict[str, str] = {
    "fact": "Independent source",
    "company_self_claim": "Company self-claim",
    "public_discourse": "Public discourse",
    "internal_document": "Internal document",
}

_SOURCE_TIER_LABELS: dict[str, str] = {
    "official": "Official register",
    "first_party": "Verified first-party",
    "secondary": "Secondary public",
    "internal_document": "Internal document",
}

_AUTOMATIC_RETRY_CODES = frozenset(
    {
        "model_schema_invalid",
        "model_timeout",
        "model_connection_failed",
        "model_rate_limited",
        "model_service_error",
        "no_sources",
        "no_valid_claims",
        "task_failed",
    }
)


def _company_display_name(
    company: CompanyModel,
    identifier: CompanyIdentifierModel | None = None,
) -> str:
    """Avoid presenting a resolved identifier as an unresolved company.

    A live discovery run can replace the placeholder with the number-addressed
    Companies House page title. Until then, this deterministic fallback is honest:
    it identifies the resolved entity without inventing its registered name.
    """

    if not company.canonical_name.startswith("Unresolved company"):
        return company.canonical_name
    if company.resolution_status == "resolved" and identifier is not None:
        return f"Company {identifier.normalized_value}"
    return company.canonical_name


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _tier_label(value: str) -> str:
    return _SOURCE_TIER_LABELS.get(value, humanize(value))


@dataclass(frozen=True, slots=True)
class NextAction:
    """The single safest action a person can take next."""

    label: str
    detail: str
    href: str | None = None

    def as_json(self) -> JsonDict:
        return {"label": self.label, "detail": self.detail, "href": self.href}


def system_state(runtime: Runtime) -> JsonDict:
    settings = runtime.settings
    reviewer = (settings.reviewer_name or "").strip()
    live = runtime.company_research is not None
    mode = runtime.research_mode
    return {
        "reviewer": reviewer or None,
        "reviewer_configured": len(reviewer) >= 2,
        "live_research_enabled": live,
        "research_mode": mode,
        "external_model_enabled": settings.allow_external_llm,
        "live_retrieval_enabled": settings.allow_live_public_retrieval,
        "model": settings.openai_model,
        "escalation_model": settings.openai_escalation_model,
        "runtime": "Loopback only · synchronous · SQLite",
        "boundary": (
            "Fixture research. Every source is a recorded synthetic page; no model "
            "call and no outbound request is made."
            if mode == "fixture"
            else "Bounded public research is live. Sources are retrieved over a "
            "DNS-pinned, robots-aware transport and snapshotted before parsing."
            if live
            else "Live retrieval and the external model are both closed by default. "
            "Open gates G2 and G4 together to enable a research run."
        ),
        "model_route": {
            "reasoning": {
                "model": settings.openai_escalation_model,
                "effort": settings.openai_reasoning_effort,
                "stages": sorted(REASONING_CAPABILITIES),
            },
            "selection": {
                "model": settings.openai_model,
                "effort": COMPANY_RESEARCH_SELECTION_EFFORT,
                "stages": ["extract_claims"],
            },
            "repair": {
                "model": settings.openai_model,
                "effort": COMPANY_RESEARCH_REPAIR_EFFORT,
                "when": "any repeat attempt after a rejected result",
            },
        },
        "budgets": {
            "max_sources": settings.company_research_max_sources,
            "max_tool_calls": settings.company_research_max_tool_calls,
            "max_source_chars": settings.company_research_max_source_chars,
            "max_corpus_chars": settings.company_research_max_corpus_chars,
            "max_output_tokens": settings.company_research_max_output_tokens,
            "max_redirects": settings.company_research_max_redirects,
            "timeout_seconds": settings.http_timeout_seconds,
            "model_timeout_seconds": settings.openai_timeout_seconds,
            "max_elapsed_seconds": settings.company_research_max_elapsed_seconds,
        },
        "agents": list(AGENT_ROLES),
    }


def _identifier_rows(session: Session, identifiers: list[CompanyIdentifierModel]) -> JsonDict:
    states: dict[str, str] = {}
    for identifier in identifiers:
        states[identifier.id] = identifier_review_projection(session, identifier).status.value
    return states


def _company_row(
    company: CompanyModel,
    *,
    identifiers: list[CompanyIdentifierModel],
    identifier_states: dict[str, str],
    domains: list[CompanyDomainModel],
    cases: list[ResearchCaseModel],
    runs: list[CompanyResearchRunModel],
    artifact_count: int,
    claim_count: int,
    live_enabled: bool,
) -> JsonDict:
    primary = next(
        (item for item in identifiers if item.scheme == "companies_house_number"),
        identifiers[0] if identifiers else None,
    )
    verified_domain = next((item for item in domains if item.status == "verified"), None)
    pending_identifiers = [
        item
        for item in identifiers
        if identifier_states.get(item.id) == IdentityCandidateStatus.PENDING.value
    ]
    pending_domains = [item for item in domains if item.status == "pending"]
    latest_run = runs[0] if runs else None
    action = _company_next_action(
        company,
        pending_identifiers=pending_identifiers,
        pending_domains=pending_domains,
        identifier_states=identifier_states,
        identifiers=identifiers,
        cases=cases,
        latest_run=latest_run,
        live_enabled=live_enabled,
    )
    return {
        "id": company.id,
        "name": _company_display_name(company, primary),
        "entity_type": company.entity_type,
        "jurisdiction": company.jurisdiction,
        "lifecycle_status": company.lifecycle_status,
        "resolution_status": company.resolution_status,
        "classification": company.classification,
        "created_at": _iso(company.created_at),
        "identifier": (
            {
                "id": primary.id,
                "scheme": primary.scheme,
                "value": primary.normalized_value,
                "state": identifier_states.get(primary.id, "unknown"),
            }
            if primary is not None
            else None
        ),
        "verified_domain": verified_domain.normalized_domain if verified_domain else None,
        "open_decisions": len(pending_identifiers) + len(pending_domains),
        "case_id": cases[0].id if cases else None,
        "case_count": len(cases),
        "artifact_count": artifact_count,
        "claim_count": claim_count,
        "run_count": len(runs),
        "latest_run": (
            {
                "id": latest_run.id,
                "status": latest_run.status,
                "cutoff": _iso(latest_run.reporting_cutoff),
                "created_at": _iso(latest_run.created_at),
            }
            if latest_run is not None
            else None
        ),
        "next_action": action.as_json(),
    }


def _company_next_action(
    company: CompanyModel,
    *,
    pending_identifiers: list[CompanyIdentifierModel],
    pending_domains: list[CompanyDomainModel],
    identifier_states: dict[str, str],
    identifiers: list[CompanyIdentifierModel],
    cases: list[ResearchCaseModel],
    latest_run: CompanyResearchRunModel | None,
    live_enabled: bool,
) -> NextAction:
    href = f"/companies/{company.id}"
    if pending_identifiers:
        return NextAction(
            "Review exact identifier",
            "A structurally valid number is still an unreviewed claim.",
            href,
        )
    if pending_domains:
        return NextAction(
            "Review domain claim",
            "The website stays self-asserted until a named decision binds it.",
            href,
        )
    if any(
        identifier_states.get(item.id) == IdentityCandidateStatus.REJECTED.value
        for item in identifiers
    ):
        return NextAction(
            "Identifier rejected",
            "Record a new exact identity claim; the rejected claim is closed.",
            href,
        )
    if company.resolution_status != "resolved":
        return NextAction(
            "Identity held",
            "Provide exact identity evidence. Nothing merges on a name.",
            href,
        )
    if latest_run is not None:
        if latest_run.status == CompanyResearchRunStatus.PENDING_REVIEW.value:
            return NextAction(
                "Review cited profile",
                "The run finished and its profile version awaits a named decision.",
                f"/runs/{latest_run.id}",
            )
        if latest_run.status in {
            CompanyResearchRunStatus.PENDING.value,
            CompanyResearchRunStatus.RUNNING.value,
        }:
            return NextAction(
                "Advance research run",
                "The next persisted stage is ready to execute.",
                f"/runs/{latest_run.id}",
            )
        if latest_run.status == CompanyResearchRunStatus.FAILED.value:
            return NextAction(
                "Inspect run failure",
                "A stage recorded a failure. Read it before retrying.",
                f"/runs/{latest_run.id}",
            )
    if cases and live_enabled:
        return NextAction(
            "Start research run",
            "The reviewed case is eligible for a bounded public research run.",
            href,
        )
    if cases:
        return NextAction(
            "Case ready · research closed",
            "Open both the live-retrieval and external-model gates to run research.",
            href,
        )
    return NextAction("No research case", "Record an authorised intake first.", href)


def companies_view(runtime: Runtime) -> JsonDict:
    live_enabled = runtime.company_research is not None
    with runtime.session_factory() as session:
        companies = list(
            session.scalars(select(CompanyModel).order_by(CompanyModel.created_at.desc())).all()
        )
        identifiers_by_company: defaultdict[str, list[CompanyIdentifierModel]] = defaultdict(list)
        for identifier in session.scalars(
            select(CompanyIdentifierModel).order_by(CompanyIdentifierModel.created_at)
        ):
            identifiers_by_company[identifier.company_id].append(identifier)
        domains_by_company: defaultdict[str, list[CompanyDomainModel]] = defaultdict(list)
        for domain in session.scalars(
            select(CompanyDomainModel).order_by(CompanyDomainModel.created_at)
        ):
            domains_by_company[domain.company_id].append(domain)
        cases_by_company: defaultdict[str, list[ResearchCaseModel]] = defaultdict(list)
        for case in session.scalars(
            select(ResearchCaseModel).order_by(ResearchCaseModel.created_at.desc())
        ):
            cases_by_company[case.company_id].append(case)
        runs_by_company: defaultdict[str, list[CompanyResearchRunModel]] = defaultdict(list)
        for run in session.scalars(
            select(CompanyResearchRunModel).order_by(CompanyResearchRunModel.created_at.desc())
        ):
            runs_by_company[run.company_id].append(run)
        artifact_counts = {
            company_id: count
            for company_id, count in session.execute(
                select(IntakeArtifactModel.company_id, func.count(IntakeArtifactModel.id)).group_by(
                    IntakeArtifactModel.company_id
                )
            ).all()
        }
        claim_counts = {
            company_id: count
            for company_id, count in session.execute(
                select(
                    CompanyResearchRunModel.company_id,
                    func.count(CompanyResearchClaimModel.id),
                )
                .join(
                    CompanyResearchClaimModel,
                    CompanyResearchClaimModel.research_run_id == CompanyResearchRunModel.id,
                )
                .group_by(CompanyResearchRunModel.company_id)
            ).all()
        }
        rows = [
            _company_row(
                company,
                identifiers=identifiers_by_company[company.id],
                identifier_states=_identifier_rows(session, identifiers_by_company[company.id]),
                domains=domains_by_company[company.id],
                cases=cases_by_company[company.id],
                runs=runs_by_company[company.id],
                artifact_count=artifact_counts.get(company.id, 0),
                claim_count=claim_counts.get(company.id, 0),
                live_enabled=live_enabled,
            )
            for company in companies
        ]
    return {
        "companies": rows,
        "counts": {
            "total": len(rows),
            "resolved": sum(row["resolution_status"] == "resolved" for row in rows),
            "identity_holds": sum(row["open_decisions"] > 0 for row in rows),
            "with_runs": sum(row["run_count"] > 0 for row in rows),
        },
    }


def _run_summary(
    run: CompanyResearchRunModel,
    *,
    company_name: str,
    tasks: list[CompanyResearchTaskModel],
    source_counts: dict[str, int],
    claim_count: int,
    profile: ProfileVersionModel | None = None,
) -> JsonDict:
    done = sum(task.status == CompanyResearchTaskStatus.SUCCEEDED.value for task in tasks)
    active = next(
        (task for task in tasks if task.status == CompanyResearchTaskStatus.RUNNING.value),
        None,
    )
    if active is None:
        active = next(
            (task for task in tasks if task.status == CompanyResearchTaskStatus.PENDING.value),
            None,
        )
    return {
        "id": run.id,
        "company_id": run.company_id,
        "company_name": company_name,
        "status": run.status,
        "cutoff": _iso(run.reporting_cutoff),
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
        "model": run.model,
        "source_policy_version": run.source_policy_version,
        "stages_total": len(tasks) or len(TASKS),
        "stages_done": done,
        "active_capability": active.capability if active is not None else None,
        "active_role": (
            _ROLE_BY_KEY.get(active.capability, {}).get("label") if active is not None else None
        ),
        "claim_count": claim_count,
        "sources": source_counts,
        "error_code": run.error_code,
        "profile": (
            {
                "id": profile.id,
                "version": profile.version,
                "status": profile.status,
                "content_sha256": profile.content_sha256,
            }
            if profile is not None
            else None
        ),
    }


def _source_counts(sources: list[CompanyResearchSourceModel]) -> dict[str, int]:
    counts = {status.value: 0 for status in ResearchSourceStatus}
    for source in sources:
        counts[source.status] = counts.get(source.status, 0) + 1
    counts["total"] = len(sources)
    return counts


def overview_view(runtime: Runtime) -> JsonDict:
    live_enabled = runtime.company_research is not None
    ledger = companies_view(runtime)
    with runtime.session_factory() as session:
        runs = list(
            session.scalars(
                select(CompanyResearchRunModel)
                .order_by(CompanyResearchRunModel.created_at.desc())
                .limit(25)
            ).all()
        )
        run_ids = [run.id for run in runs]
        names = {row["id"]: row["name"] for row in ledger["companies"]}
        tasks_by_run: defaultdict[str, list[CompanyResearchTaskModel]] = defaultdict(list)
        sources_by_run: defaultdict[str, list[CompanyResearchSourceModel]] = defaultdict(list)
        claims_by_run: defaultdict[str, int] = defaultdict(int)
        profiles_by_run: dict[str, ProfileVersionModel] = {}
        if run_ids:
            for task in session.scalars(
                select(CompanyResearchTaskModel)
                .where(CompanyResearchTaskModel.research_run_id.in_(run_ids))
                .order_by(CompanyResearchTaskModel.stage_order)
            ):
                tasks_by_run[task.research_run_id].append(task)
            for source in session.scalars(
                select(CompanyResearchSourceModel).where(
                    CompanyResearchSourceModel.research_run_id.in_(run_ids)
                )
            ):
                sources_by_run[source.research_run_id].append(source)
            for run_id, count in session.execute(
                select(
                    CompanyResearchClaimModel.research_run_id,
                    func.count(CompanyResearchClaimModel.id),
                )
                .where(CompanyResearchClaimModel.research_run_id.in_(run_ids))
                .group_by(CompanyResearchClaimModel.research_run_id)
            ).all():
                claims_by_run[run_id] = count
            for profile in session.scalars(
                select(ProfileVersionModel).where(
                    ProfileVersionModel.research_run_id.in_(run_ids)
                )
            ):
                if profile.research_run_id is not None:
                    profiles_by_run[profile.research_run_id] = profile
        pending_profiles = list(
            session.scalars(
                select(ProfileVersionModel)
                .where(ProfileVersionModel.status == ProfileVersionStatus.PENDING_REVIEW.value)
                .order_by(ProfileVersionModel.created_at.desc())
            ).all()
        )
        run_rows = [
            _run_summary(
                run,
                company_name=names.get(run.company_id, "Unknown company"),
                tasks=tasks_by_run[run.id],
                source_counts=_source_counts(sources_by_run[run.id]),
                claim_count=claims_by_run[run.id],
                profile=profiles_by_run.get(run.id),
            )
            for run in runs
        ]

    attention: list[JsonDict] = []
    for row in ledger["companies"]:
        if row["open_decisions"]:
            attention.append(
                {
                    "id": f"identity-{row['id']}",
                    "kind": "Identity",
                    "severity": "hold",
                    "title": row["name"],
                    "detail": f"{row['open_decisions']} unreviewed identity claim(s).",
                    "action_label": "Open company",
                    "href": f"/companies/{row['id']}",
                }
            )
    for row in run_rows:
        if row["status"] == CompanyResearchRunStatus.PENDING_REVIEW.value:
            attention.append(
                {
                    "id": f"review-{row['id']}",
                    "kind": "Review",
                    "severity": "review",
                    "title": row["company_name"],
                    "detail": "A cited profile version awaits a named decision.",
                    "action_label": "Open run",
                    "href": f"/runs/{row['id']}",
                }
            )
        elif row["status"] == CompanyResearchRunStatus.FAILED.value:
            attention.append(
                {
                    "id": f"failed-{row['id']}",
                    "kind": "Failure",
                    "severity": "danger",
                    "title": row["company_name"],
                    "detail": f"Stage failure recorded: {row['error_code'] or 'not recorded'}.",
                    "action_label": "Inspect run",
                    "href": f"/runs/{row['id']}",
                }
            )
        elif row["status"] in {
            CompanyResearchRunStatus.PENDING.value,
            CompanyResearchRunStatus.RUNNING.value,
        }:
            attention.append(
                {
                    "id": f"active-{row['id']}",
                    "kind": "Execution",
                    "severity": "active",
                    "title": row["company_name"],
                    "detail": (
                        f"{row['stages_done']}/{row['stages_total']} stages complete · "
                        f"next: {row['active_role'] or 'not recorded'}"
                    ),
                    "action_label": "Open control room",
                    "href": f"/runs/{row['id']}",
                }
            )
        blocked = row["sources"].get("blocked", 0) + row["sources"].get("failed", 0)
        if blocked:
            attention.append(
                {
                    "id": f"sources-{row['id']}",
                    "kind": "Coverage",
                    "severity": "warning",
                    "title": row["company_name"],
                    "detail": (
                        f"{blocked} source(s) blocked or failed and are absent from evidence."
                    ),
                    "action_label": "Open run",
                    "href": f"/runs/{row['id']}",
                }
            )

    severity_order = {"danger": 0, "hold": 1, "review": 2, "active": 3, "warning": 4}
    attention.sort(key=lambda item: severity_order.get(str(item["severity"]), 9))

    identity_holds = ledger["counts"]["identity_holds"]
    active_runs = sum(
        row["status"]
        in {CompanyResearchRunStatus.PENDING.value, CompanyResearchRunStatus.RUNNING.value}
        for row in run_rows
    )
    if identity_holds:
        next_action = NextAction(
            f"Resolve {identity_holds} identity hold(s)",
            "Nothing collects evidence until the exact legal entity is accepted.",
            "/companies",
        )
    elif pending_profiles:
        next_action = NextAction(
            f"Review {len(pending_profiles)} profile version(s)",
            "A completed run is waiting on the only role that can approve.",
            f"/runs/{pending_profiles[0].research_run_id}"
            if pending_profiles[0].research_run_id
            else "/companies",
        )
    elif active_runs:
        next_action = NextAction(
            f"Advance {active_runs} running case(s)",
            "The orchestrator executes one persisted stage per instruction.",
            "/companies",
        )
    elif not ledger["companies"]:
        next_action = NextAction(
            "Register a company number",
            "A Companies House number alone opens a research case.",
            "/companies",
        )
    else:
        next_action = NextAction(
            "Start a research run",
            "Every reviewed case is eligible for a bounded public research run.",
            "/companies",
        )

    return {
        "system": system_state(runtime),
        "next_action": next_action.as_json(),
        "metrics": {
            "companies": ledger["counts"]["total"],
            "resolved": ledger["counts"]["resolved"],
            "identity_holds": identity_holds,
            "runs_total": len(run_rows),
            "runs_active": active_runs,
            "runs_pending_review": sum(
                row["status"] == CompanyResearchRunStatus.PENDING_REVIEW.value for row in run_rows
            ),
            "claims": sum(int(row["claim_count"]) for row in run_rows),
            "sources_captured": sum(int(row["sources"].get("fetched", 0)) for row in run_rows),
            "sources_withheld": sum(
                int(row["sources"].get("blocked", 0))
                + int(row["sources"].get("failed", 0))
                + int(row["sources"].get("unsupported", 0))
                for row in run_rows
            ),
        },
        "attention": attention[:12],
        "runs": run_rows,
        "companies": ledger["companies"],
        "live_research_enabled": live_enabled,
    }


def _attempt_rows(attempts: list[CompanyResearchTaskAttemptModel]) -> list[JsonDict]:
    return [
        {
            "attempt": attempt.attempt_number,
            "status": attempt.status,
            "model": attempt.model,
            "input_hash": attempt.input_hash,
            "output_hash": attempt.output_hash,
            "input_tokens": attempt.input_tokens,
            "output_tokens": attempt.output_tokens,
            "tool_calls": attempt.tool_calls,
            "duration_ms": attempt.duration_ms,
            "error_code": attempt.error_code,
            "error_message": attempt.error_message,
            "created_at": _iso(attempt.created_at),
        }
        for attempt in attempts
    ]


def _task_outputs(
    capability: str,
    *,
    sources: list[CompanyResearchSourceModel],
    claims: list[CompanyResearchClaimModel],
    profile: ProfileVersionModel | None,
) -> list[JsonDict]:
    counts = _source_counts(sources)
    if capability == "discover_sources":
        domains = sorted({source.publisher_domain for source in sources})
        return [
            {"label": "Candidate sources", "value": counts["total"]},
            {"label": "Distinct publishers", "value": len(domains)},
            {
                "label": "Official register candidates",
                "value": sum(source.source_tier == "official" for source in sources),
            },
        ]
    if capability == "capture_sources":
        return [
            {"label": "Captured", "value": counts.get("fetched", 0)},
            {"label": "Blocked by policy", "value": counts.get("blocked", 0)},
            {"label": "Unsupported media", "value": counts.get("unsupported", 0)},
            {"label": "Fetch failed", "value": counts.get("failed", 0)},
            {
                "label": "Contact redactions",
                "value": sum(source.redaction_count for source in sources),
            },
        ]
    if capability == "extract_claims":
        perspectives: defaultdict[str, int] = defaultdict(int)
        for claim in claims:
            perspectives[claim.perspective] += 1
        rows = [{"label": "Claims admitted", "value": len(claims)}]
        rows.extend(
            {"label": _PERSPECTIVE_LABELS.get(key, humanize(key)), "value": value}
            for key, value in sorted(perspectives.items())
        )
        return rows
    if capability == "compose_deck":
        content = profile.content_json if profile is not None else {}
        coverage = content.get("coverage", {}) if isinstance(content, dict) else {}
        return [
            {"label": "Profile version", "value": profile.version if profile else "Not recorded"},
            {
                "label": "Sections with evidence",
                "value": len(coverage.get("covered_categories", []) or []),
            },
            {
                "label": "Contradictions raised",
                "value": coverage.get("contradiction_candidates", 0),
            },
            {"label": "Content SHA-256", "value": profile.content_sha256 if profile else None},
        ]
    return []


def _lane_rows(
    sources: list[CompanyResearchSourceModel],
    claims_by_source: dict[str, int],
) -> list[JsonDict]:
    return [
        {
            "id": source.id,
            "url": source.final_url or source.url,
            "requested_url": source.url,
            "title": source.title,
            "publisher_domain": source.publisher_domain,
            "source_tier": source.source_tier,
            "source_tier_label": _tier_label(source.source_tier),
            "origin": source.origin,
            "entity_scope": source.entity_scope,
            "status": source.status,
            "http_status": source.http_status,
            "media_type": source.media_type,
            "byte_size": source.byte_size,
            "raw_sha256": source.raw_sha256,
            "snapshot_kind": source.snapshot_kind,
            "redaction_count": source.redaction_count,
            "retrieved_at": _iso(source.retrieved_at),
            "error_code": source.error_code,
            "error_message": source.error_message,
            "claim_count": claims_by_source.get(source.id, 0),
        }
        for source in sources
    ]


def _claim_rows(claims: list[CompanyResearchClaimModel]) -> list[JsonDict]:
    return [
        {
            "id": claim.id,
            "source_id": claim.research_source_id,
            "category": claim.category,
            "category_label": _CLAIM_CATEGORY_LABELS.get(claim.category, humanize(claim.category)),
            "entity_scope": claim.entity_scope,
            "subject_key": claim.subject_key,
            "statement": claim.statement,
            "evidence_span": claim.evidence_span,
            "source_locator": claim.source_locator,
            "event_date": claim.event_date,
            "amount": claim.amount,
            "currency": claim.currency,
            "perspective": claim.perspective,
            "perspective_label": _PERSPECTIVE_LABELS.get(
                claim.perspective, humanize(claim.perspective)
            ),
            "verification_status": claim.verification_status,
            "extraction_method": claim.extraction_method,
            "model": claim.model,
        }
        for claim in claims
    ]


def _gate_node(
    key: str,
    *,
    status: str,
    detail: str,
    outputs: list[JsonDict] | None = None,
) -> JsonDict:
    role = _ROLE_BY_KEY[key]
    return {
        "id": key,
        "kind": "gate",
        "label": role["label"],
        "layer": role["layer"],
        "engine": role["engine"],
        "status": status,
        "detail": detail,
        "summary": role["summary"],
        "contract": {
            "owns": role["owns"],
            "must_not": role["must_not"],
            "inputs": role["inputs"],
            "outputs": role["outputs"],
        },
        "attempts": None,
        "route": None,
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "input_hash": None,
        "output_hash": None,
        "outputs_summary": outputs or [],
        "attempt_log": [],
        "error": None,
        "lane_count": 0,
    }


def run_view(runtime: Runtime, run_id: str) -> JsonDict:
    with runtime.session_factory() as session:
        run = session.get(CompanyResearchRunModel, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Unknown research run.")
        company = session.get(CompanyModel, run.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Research run has no company record.")
        identifier = session.scalar(
            select(CompanyIdentifierModel).where(
                CompanyIdentifierModel.company_id == company.id,
                CompanyIdentifierModel.scheme == "companies_house_number",
            )
        )
        tasks = list(
            session.scalars(
                select(CompanyResearchTaskModel)
                .where(CompanyResearchTaskModel.research_run_id == run.id)
                .order_by(CompanyResearchTaskModel.stage_order)
            ).all()
        )
        attempts_by_task: defaultdict[str, list[CompanyResearchTaskAttemptModel]] = defaultdict(
            list
        )
        if tasks:
            for attempt in session.scalars(
                select(CompanyResearchTaskAttemptModel)
                .where(
                    CompanyResearchTaskAttemptModel.research_task_id.in_(
                        [task.id for task in tasks]
                    )
                )
                .order_by(CompanyResearchTaskAttemptModel.attempt_number)
            ):
                attempts_by_task[attempt.research_task_id].append(attempt)
        sources = list(
            session.scalars(
                select(CompanyResearchSourceModel)
                .where(CompanyResearchSourceModel.research_run_id == run.id)
                .order_by(
                    CompanyResearchSourceModel.source_tier,
                    CompanyResearchSourceModel.created_at,
                )
            ).all()
        )
        claims = list(
            session.scalars(
                select(CompanyResearchClaimModel)
                .where(CompanyResearchClaimModel.research_run_id == run.id)
                .order_by(
                    CompanyResearchClaimModel.category,
                    CompanyResearchClaimModel.created_at,
                )
            ).all()
        )
        profile = session.scalar(
            select(ProfileVersionModel).where(ProfileVersionModel.research_run_id == run.id)
        )
        if profile is not None:
            validated_profile_content(profile)
        claims_by_source: dict[str, int] = defaultdict(int)
        for claim in claims:
            claims_by_source[claim.research_source_id] += 1

        nodes: list[JsonDict] = [
            _gate_node(
                "identity",
                status="succeeded",
                detail=(
                    f"Accepted Companies House number {identifier.normalized_value}"
                    if identifier is not None
                    else "No Companies House identifier is recorded."
                ),
                outputs=[
                    {
                        "label": "Company name",
                        "value": _company_display_name(company, identifier),
                    },
                    {
                        "label": "Company number",
                        "value": identifier.normalized_value if identifier else None,
                    },
                    {"label": "Resolution", "value": humanize(company.resolution_status)},
                ],
            )
        ]
        for task in tasks:
            role = _ROLE_BY_KEY.get(
                task.capability,
                {
                    "label": humanize(task.capability),
                    "layer": "Execution",
                    "engine": "deterministic",
                    "summary": "",
                    "owns": "",
                    "must_not": "",
                    "inputs": "",
                    "outputs": "",
                },
            )
            attempts = attempts_by_task[task.id]
            latest = attempts[-1] if attempts else None
            route_attempt = (
                task.attempt_count + 1
                if task.status == CompanyResearchTaskStatus.PENDING.value
                else max(1, task.attempt_count)
            )
            planned_model, planned_effort = route_for(
                runtime.settings, task.capability, route_attempt
            )
            nodes.append(
                {
                    "id": task.capability,
                    "kind": "task",
                    "label": role["label"],
                    "layer": role["layer"],
                    "engine": role["engine"],
                    "status": task.status,
                    "detail": _task_detail(task, sources=sources, claims=claims),
                    "summary": role["summary"],
                    "contract": {
                        "owns": role["owns"],
                        "must_not": role["must_not"],
                        "inputs": role["inputs"],
                        "outputs": role["outputs"],
                    },
                    "attempts": {"count": task.attempt_count, "max": task.max_attempts},
                    "route": (
                        {
                            "tier": (
                                "reasoning"
                                if task.capability in REASONING_CAPABILITIES
                                and route_attempt == 1
                                else "repair"
                                if route_attempt > 1
                                else "small"
                            ),
                            "model": (
                                latest.model
                                if latest is not None and latest.model
                                else planned_model
                            ),
                            "effort": planned_effort,
                        }
                        if role["engine"] == "model"
                        else None
                    ),
                    "started_at": _iso(task.started_at),
                    "finished_at": _iso(task.finished_at),
                    "duration_ms": latest.duration_ms if latest is not None else None,
                    "input_hash": task.input_hash,
                    "output_hash": task.output_hash,
                    "outputs_summary": _task_outputs(
                        task.capability, sources=sources, claims=claims, profile=profile
                    ),
                    "attempt_log": _attempt_rows(attempts),
                    "error": (
                        {"code": task.error_code, "message": task.error_message}
                        if task.error_code
                        else None
                    ),
                    "lane_count": len(sources) if task.capability == "capture_sources" else 0,
                }
            )
        review_status = "pending"
        review_detail = "Composition has not produced a profile version yet."
        composition_complete = any(
            task.capability == "compose_deck"
            and task.status == CompanyResearchTaskStatus.SUCCEEDED.value
            for task in tasks
        )
        if profile is not None:
            if (
                profile.status == ProfileVersionStatus.PENDING_REVIEW.value
                and composition_complete
            ):
                review_status = "awaiting"
                review_detail = "Version awaits the named reviewer."
            elif profile.status == ProfileVersionStatus.PENDING_REVIEW.value:
                review_detail = (
                    "A profile version exists, but task finalization is incomplete. "
                    "Recover the interrupted stage before review."
                )
            elif profile.status == ProfileVersionStatus.APPROVED.value:
                review_status = "succeeded"
                review_detail = f"Approved by {profile.reviewed_by or 'a named reviewer'}."
            elif profile.status == ProfileVersionStatus.REJECTED.value:
                review_status = "failed"
                review_detail = f"Rejected by {profile.reviewed_by or 'a named reviewer'}."
        nodes.append(
            _gate_node(
                "human_review",
                status=review_status,
                detail=review_detail,
                outputs=[
                    {"label": "Profile version", "value": profile.version if profile else None},
                    {
                        "label": "Status",
                        "value": humanize(profile.status) if profile else "Not created",
                    },
                    {"label": "Reviewer", "value": profile.reviewed_by if profile else None},
                ],
            )
        )
        edges = [
            {"from": nodes[index]["id"], "to": nodes[index + 1]["id"], "kind": "spine"}
            for index in range(len(nodes) - 1)
        ]
        content = profile.content_json if profile is not None else {}
        return {
            "run": {
                "id": run.id,
                "company_id": run.company_id,
                "company_name": _company_display_name(company, identifier),
                "company_number": identifier.normalized_value if identifier else None,
                "research_case_id": run.research_case_id,
                "status": run.status,
                "cutoff": _iso(run.reporting_cutoff),
                "created_at": _iso(run.created_at),
                "updated_at": _iso(run.updated_at),
                "created_by": run.created_by,
                "model": run.model,
                "prompt_version": run.prompt_version,
                "source_policy_version": run.source_policy_version,
                "request_fingerprint": run.request_fingerprint,
                "budgets": run.budgets_json,
                "usage": run.usage_json,
                "coverage": run.coverage_json,
                "cancelled_by": run.cancelled_by,
                "cancellation_reason": run.cancellation_reason,
                "error_code": run.error_code,
                "error_message": run.error_message,
            },
            "nodes": nodes,
            "edges": edges,
            "lanes": _lane_rows(sources, dict(claims_by_source)),
            "claims": _claim_rows(claims),
            "profile": _profile_json(profile),
            "contradictions": (
                content.get("contradictions", []) if isinstance(content, dict) else []
            ),
            "limitations": content.get("limitations", []) if isinstance(content, dict) else [],
            "next_action": _run_next_action(run, profile=profile).as_json(),
        }


def _task_detail(
    task: CompanyResearchTaskModel,
    *,
    sources: list[CompanyResearchSourceModel],
    claims: list[CompanyResearchClaimModel],
) -> str:
    counts = _source_counts(sources)
    if task.status == CompanyResearchTaskStatus.PENDING.value:
        return "Waiting for the orchestrator to claim this stage."
    if task.status == CompanyResearchTaskStatus.RUNNING.value:
        return "Executing now. The stage holds an exclusive claim on this run."
    if task.status == CompanyResearchTaskStatus.FAILED.value:
        return task.error_message or "Recorded a failure without a safe message."
    if task.status == CompanyResearchTaskStatus.CANCELLED.value:
        return "Cancelled by a named reviewer before completion."
    if task.capability == "discover_sources":
        return f"Recorded {counts['total']} candidate source(s). No content was read."
    if task.capability == "capture_sources":
        return (
            f"Captured {counts.get('fetched', 0)} of {counts['total']} candidates as "
            "checksummed snapshots."
        )
    if task.capability == "extract_claims":
        return f"Admitted {len(claims)} claim(s), each a verbatim span of a captured snapshot."
    if task.capability == "compose_deck":
        return "Composed one profile version and stopped at the human review boundary."
    return "Stage complete."


def _profile_json(profile: ProfileVersionModel | None) -> JsonDict | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "version": profile.version,
        "status": profile.status,
        "content_sha256": profile.content_sha256,
        "created_by": profile.created_by,
        "reviewed_by": profile.reviewed_by,
        "review_reason": profile.review_reason,
        "lock_version": profile.lock_version,
        "created_at": _iso(profile.created_at),
        "content": profile.content_json,
    }


def _run_next_action(
    run: CompanyResearchRunModel, *, profile: ProfileVersionModel | None
) -> NextAction:
    if run.status == CompanyResearchRunStatus.PENDING_REVIEW.value and profile is not None:
        return NextAction(
            "Approve or reject version " + str(profile.version),
            "Approval records review of this version. It does not upgrade held evidence.",
        )
    if run.status in {
        CompanyResearchRunStatus.PENDING.value,
        CompanyResearchRunStatus.RUNNING.value,
    }:
        return NextAction(
            "Advance the next stage",
            "The orchestrator executes exactly one persisted stage per instruction.",
        )
    if run.status == CompanyResearchRunStatus.FAILED.value:
        return NextAction(
            "Inspect the recorded failure",
            "Contract and trust failures are never retried automatically.",
        )
    if run.status == CompanyResearchRunStatus.CANCELLED.value:
        return NextAction("Run cancelled", run.cancellation_reason or "No rationale recorded.")
    if run.status == CompanyResearchRunStatus.APPROVED.value:
        return NextAction("Approved", "The profile version is locked under a named decision.")
    if run.status == CompanyResearchRunStatus.REJECTED.value:
        return NextAction("Rejected", "Start a new run to produce another version.")
    return NextAction("No action recorded", "This run has no outstanding step.")


def _advance_failure_payload(state: JsonDict, exc: Exception, *, elapsed_ms: int) -> JsonDict:
    failed = next(
        (
            node
            for node in state.get("nodes", [])
            if node.get("kind") == "task" and node.get("status") == "failed"
        ),
        None,
    )
    attempts = failed.get("attempts") if isinstance(failed, dict) else None
    used = int(attempts.get("count", 0)) if isinstance(attempts, dict) else 0
    maximum = int(attempts.get("max", 0)) if isinstance(attempts, dict) else 0
    remaining = max(0, maximum - used)
    code = getattr(exc, "code", None) or state.get("run", {}).get("error_code") or "task_failed"
    recorded_message = state.get("run", {}).get("error_message")
    message = (
        str(recorded_message)
        if recorded_message
        else str(exc)
        if isinstance(exc, CompanyResearchError)
        else "The stage failed and the safe error was recorded."
    )
    return {
        "ok": False,
        "capability": failed.get("id") if isinstance(failed, dict) else None,
        "code": code,
        "message": message,
        "elapsed_ms": elapsed_ms,
        "retryable": code in _AUTOMATIC_RETRY_CODES and remaining > 0,
        "attempts_remaining": remaining,
    }


def company_view(runtime: Runtime, company_id: str) -> JsonDict:
    live_enabled = runtime.company_research is not None
    with runtime.session_factory() as session:
        company = session.get(CompanyModel, company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Unknown company.")
        identifiers = list(
            session.scalars(
                select(CompanyIdentifierModel)
                .where(CompanyIdentifierModel.company_id == company_id)
                .order_by(CompanyIdentifierModel.created_at)
            ).all()
        )
        identifier_states = _identifier_rows(session, identifiers)
        identifier_rows = [
            {
                "id": item.id,
                "scheme": item.scheme,
                "scheme_label": humanize(item.scheme),
                "value": item.normalized_value,
                "submitted_value": item.value,
                "reviewed": item.reviewed,
                "state": identifier_states.get(item.id, "unknown"),
                "created_at": _iso(item.created_at),
            }
            for item in identifiers
        ]
        domains = list(
            session.scalars(
                select(CompanyDomainModel)
                .where(CompanyDomainModel.company_id == company_id)
                .order_by(CompanyDomainModel.created_at)
            ).all()
        )
        domain_rows = [
            {
                "id": item.id,
                "url": item.url,
                "domain": item.normalized_domain,
                "status": item.status,
                "created_at": _iso(item.created_at),
            }
            for item in domains
        ]
        relationships = list(
            session.scalars(
                select(CompanyRelationshipModel)
                .where(CompanyRelationshipModel.subject_company_id == company_id)
                .order_by(CompanyRelationshipModel.created_at)
            ).all()
        )
        relationship_rows = []
        for item in relationships:
            related = session.get(CompanyModel, item.related_company_id)
            related_identifier = session.scalar(
                select(CompanyIdentifierModel).where(
                    CompanyIdentifierModel.company_id == item.related_company_id,
                    CompanyIdentifierModel.scheme == "companies_house_number",
                )
            )
            relationship_rows.append(
                {
                    "id": item.id,
                    "relationship_type": item.relationship_type,
                    "status": item.status,
                    "related_company_id": item.related_company_id,
                    "related_company_name": related.canonical_name if related else "Unavailable",
                    "companies_house_number": (
                        related_identifier.normalized_value if related_identifier else None
                    ),
                    "proposed_by": item.proposed_by,
                    "created_at": _iso(item.created_at),
                }
            )
        cases = list(
            session.scalars(
                select(ResearchCaseModel)
                .where(ResearchCaseModel.company_id == company_id)
                .order_by(ResearchCaseModel.created_at.desc())
            ).all()
        )
        case_rows = [
            {
                "id": item.id,
                "purpose": item.purpose,
                "classification": item.classification,
                "evidence_scope": EvidenceScope.LEGAL_ENTITY.value,
                "processing_boundary": None,
                "status": item.status,
                "created_at": _iso(item.created_at),
                "created_by": item.created_by,
            }
            for item in cases
        ]
        artifacts = list(
            session.scalars(
                select(IntakeArtifactModel)
                .where(IntakeArtifactModel.company_id == company_id)
                .order_by(IntakeArtifactModel.created_at.desc())
            ).all()
        )
        artifact_rows = [
            {
                "id": item.id,
                "kind": item.kind,
                "kind_label": humanize(item.kind),
                "normalized_value": item.normalized_value,
                "original_filename": item.original_filename,
                "classification": item.classification,
                "content_sha256": item.content_sha256,
                "actor": item.actor,
                "created_at": _iso(item.created_at),
            }
            for item in artifacts
        ]
        runs = list(
            session.scalars(
                select(CompanyResearchRunModel)
                .where(CompanyResearchRunModel.company_id == company_id)
                .order_by(CompanyResearchRunModel.created_at.desc())
            ).all()
        )
        run_ids = [item.id for item in runs]
        tasks_by_run: defaultdict[str, list[CompanyResearchTaskModel]] = defaultdict(list)
        sources_by_run: defaultdict[str, list[CompanyResearchSourceModel]] = defaultdict(list)
        claims_by_run: defaultdict[str, list[CompanyResearchClaimModel]] = defaultdict(list)
        profiles_by_run: dict[str, ProfileVersionModel] = {}
        if run_ids:
            for task in session.scalars(
                select(CompanyResearchTaskModel)
                .where(CompanyResearchTaskModel.research_run_id.in_(run_ids))
                .order_by(CompanyResearchTaskModel.stage_order)
            ):
                tasks_by_run[task.research_run_id].append(task)
            for source in session.scalars(
                select(CompanyResearchSourceModel).where(
                    CompanyResearchSourceModel.research_run_id.in_(run_ids)
                )
            ):
                sources_by_run[source.research_run_id].append(source)
            for claim in session.scalars(
                select(CompanyResearchClaimModel)
                .where(CompanyResearchClaimModel.research_run_id.in_(run_ids))
                .order_by(
                    CompanyResearchClaimModel.category, CompanyResearchClaimModel.created_at
                )
            ):
                claims_by_run[claim.research_run_id].append(claim)
            for profile in session.scalars(
                select(ProfileVersionModel).where(
                    ProfileVersionModel.research_run_id.in_(run_ids)
                )
            ):
                if profile.research_run_id is not None:
                    profiles_by_run[profile.research_run_id] = profile
        run_rows = [
            _run_summary(
                item,
                company_name=company.canonical_name,
                tasks=tasks_by_run[item.id],
                source_counts=_source_counts(sources_by_run[item.id]),
                claim_count=len(claims_by_run[item.id]),
                profile=profiles_by_run.get(item.id),
            )
            for item in runs
        ]
        profiles = (
            list(
                session.scalars(
                    select(ProfileVersionModel)
                    .where(
                        ProfileVersionModel.research_case_id.in_([item.id for item in cases])
                    )
                    .order_by(ProfileVersionModel.created_at.desc())
                ).all()
            )
            if cases
            else []
        )
        for profile in profiles:
            if profile.research_run_id is not None:
                try:
                    validated_profile_content(profile)
                except CompanyResearchError:
                    # A hash mismatch must not blank the company page. Export
                    # routes still validate before a download.
                    continue
        current_profile = next(
            (item for item in profiles if item.status == ProfileVersionStatus.APPROVED.value),
            profiles[0] if profiles else None,
        )
        latest_run = runs[0] if runs else None
        latest_claims = claims_by_run[latest_run.id] if latest_run is not None else []
        latest_sources = sources_by_run[latest_run.id] if latest_run is not None else []
        sections: list[JsonDict] = []
        grouped: defaultdict[str, list[CompanyResearchClaimModel]] = defaultdict(list)
        for claim in latest_claims:
            grouped[claim.category].append(claim)
        for category in ResearchClaimCategory:
            rows = grouped.get(category.value, [])
            sections.append(
                {
                    "key": category.value,
                    "label": _CLAIM_CATEGORY_LABELS.get(category.value, humanize(category.value)),
                    "claims": _claim_rows(rows),
                    "count": len(rows),
                }
            )
        pending_identifiers = [
            item
            for item in identifiers
            if identifier_states.get(item.id) == IdentityCandidateStatus.PENDING.value
        ]
        action = _company_next_action(
            company,
            pending_identifiers=pending_identifiers,
            pending_domains=[item for item in domains if item.status == "pending"],
            identifier_states=identifier_states,
            identifiers=identifiers,
            cases=cases,
            latest_run=latest_run,
            live_enabled=live_enabled,
        )
        return {
            "company": {
                "id": company.id,
                "name": _company_display_name(
                    company,
                    next(
                        (
                            item
                            for item in identifiers
                            if item.scheme == "companies_house_number"
                        ),
                        identifiers[0] if identifiers else None,
                    ),
                ),
                "entity_type": company.entity_type,
                "jurisdiction": company.jurisdiction,
                "lifecycle_status": company.lifecycle_status,
                "resolution_status": company.resolution_status,
                "classification": company.classification,
                "created_at": _iso(company.created_at),
            },
            "identifiers": identifier_rows,
            "domains": domain_rows,
            "relationships": relationship_rows,
            "cases": case_rows,
            "artifacts": artifact_rows,
            "runs": run_rows,
            "sections": sections,
            "investment_report": build_investment_report(latest_claims),
            "investment_reports": {
                "legal_entity": build_investment_report(
                    latest_claims, entity_scope="legal_entity"
                ),
                "consolidated_group": build_investment_report(
                    latest_claims, entity_scope="consolidated_group"
                ),
            },
            "lanes": _lane_rows(
                latest_sources,
                {
                    source_id: sum(
                        claim.research_source_id == source_id for claim in latest_claims
                    )
                    for source_id in {claim.research_source_id for claim in latest_claims}
                },
            ),
            "profile": _profile_json(current_profile),
            "profile_versions": [
                {
                    "id": item.id,
                    "version": item.version,
                    "status": item.status,
                    "created_at": _iso(item.created_at),
                    "reviewed_by": item.reviewed_by,
                    "content_sha256": item.content_sha256,
                    "research_run_id": item.research_run_id,
                }
                for item in profiles
            ],
            "next_action": action.as_json(),
            "live_research_enabled": live_enabled,
        }


def create_api_router(
    runtime: Runtime,
    *,
    csrf_token: str,
    csrf_cookie: str,
) -> APIRouter:
    """Build the JSON router used by the control-room front end.

    Mutations use a double-submit CSRF contract: the token must match both the
    cookie and the process token. The reviewer identity still
    comes from local configuration and is never accepted from the request.
    """

    router = APIRouter(prefix="/api")

    def require_csrf(request: Request, submitted: str | None) -> None:
        token = submitted or request.headers.get("x-csrf-token", "")
        cookie = request.cookies.get(csrf_cookie, "")
        if not (
            hmac.compare_digest(token, csrf_token) and hmac.compare_digest(cookie, csrf_token)
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")

    def reviewer_identity() -> str:
        reviewer = (runtime.settings.reviewer_name or "").strip()
        if len(reviewer) < 2:
            raise HTTPException(
                status_code=403,
                detail="Set PORTFOLIO_REVIEWER_NAME before using review actions.",
            )
        return reviewer

    def reporting_cutoff(payload: JsonDict) -> date:
        raw_cutoff = str(payload.get("reporting_cutoff") or "").strip()
        if not raw_cutoff:
            return date.today()
        try:
            return date.fromisoformat(raw_cutoff)
        except ValueError as exc:
            raise domain_error(
                CompanyResearchError("Research cutoff must use YYYY-MM-DD.")
            ) from exc

    def research_service() -> Any:
        if runtime.company_research is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Live company research is closed. Open PORTFOLIO_ALLOW_LIVE_PUBLIC_RETRIEVAL "
                    "and PORTFOLIO_ALLOW_EXTERNAL_LLM together, then restart."
                ),
            )
        return runtime.company_research

    def domain_error(exc: Exception) -> HTTPException:
        code = getattr(exc, "code", "domain_error")
        return HTTPException(status_code=422, detail={"message": str(exc), "code": code})

    @router.get("/session")
    def session_state(request: Request) -> JsonDict:
        del request
        return {"csrf_token": csrf_token, "system": system_state(runtime)}

    @router.get("/overview")
    def overview() -> JsonDict:
        return overview_view(runtime)

    @router.get("/companies")
    def companies() -> JsonDict:
        return companies_view(runtime)

    @router.get("/companies/{company_id}")
    def company_detail(company_id: str) -> JsonDict:
        return company_view(runtime, company_id)

    @router.get("/research-runs/{run_id}")
    def research_run(run_id: str) -> JsonDict:
        return run_view(runtime, run_id)

    @router.post("/company-intakes", status_code=201)
    def create_intake(
        request: Request,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        actor = reviewer_identity()
        try:
            classification = DataClassification(
                str(payload.get("classification") or DataClassification.PUBLIC.value)
            )
        except ValueError as exc:
            raise domain_error(
                CompanyIntakeValidationError("Unsupported data classification.")
            ) from exc

        def field(name: str) -> str | None:
            value = payload.get(name)
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        try:
            result = runtime.intakes.create(
                CompanyIntakeRequest(
                    actor=actor,
                    purpose=str(payload.get("purpose") or ""),
                    classification=classification,
                    companies_house_number=field("companies_house_number"),
                    website=field("website"),
                    company_name=field("company_name"),
                    jurisdiction=field("jurisdiction"),
                )
            )
        except CompanyIntakeValidationError as exc:
            raise domain_error(exc) from exc
        return {
            "company_id": result.company_id,
            "research_case_id": result.research_case_id,
            "company": company_view(runtime, result.company_id),
        }

    @router.post("/research-cases/{research_case_id}/documents", status_code=201)
    async def attach_documents(
        request: Request,
        research_case_id: str,
        files: Annotated[list[UploadFile], File()],
        classification: Annotated[str, Form()] = DataClassification.INTERNAL.value,
        evidence_scope: Annotated[str, Form()] = EvidenceScope.LEGAL_ENTITY.value,
    ) -> JsonDict:
        require_csrf(request, request.headers.get("x-csrf-token"))
        if not 1 <= len(files) <= MAX_DOCUMENTS_PER_BATCH:
            raise domain_error(
                CompanyIntakeValidationError("Upload between 1 and 12 documents per batch.")
            )
        try:
            selected_classification = DataClassification(classification)
            selected_scope = EvidenceScope(evidence_scope)
        except ValueError as exc:
            raise domain_error(
                CompanyIntakeValidationError("Unsupported document classification or scope.")
            ) from exc
        uploads: list[CompanyDocumentUpload] = []
        for uploaded in files:
            uploads.append(
                CompanyDocumentUpload(
                    content=await uploaded.read(),
                    filename=uploaded.filename or "document.bin",
                    declared_mime=uploaded.content_type,
                )
            )
        try:
            results = runtime.intakes.attach_documents(
                research_case_id,
                tuple(uploads),
                actor=reviewer_identity(),
                classification=selected_classification,
                evidence_scope=selected_scope,
            )
        except CompanyIntakeValidationError as exc:
            raise domain_error(exc) from exc
        company_id = results[0].company_id
        return {
            "uploaded": len(results),
            "reused": sum(item.reused_existing for item in results),
            "company": company_view(runtime, company_id),
        }

    @router.post("/companies/{company_id}/group-scopes", status_code=201)
    def propose_group_scope(
        request: Request,
        company_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        try:
            runtime.intakes.propose_group_scope(
                company_id=company_id,
                companies_house_number=str(payload.get("companies_house_number") or ""),
                company_name=str(payload.get("company_name") or "") or None,
                actor=reviewer_identity(),
            )
        except CompanyIntakeValidationError as exc:
            raise domain_error(exc) from exc
        return company_view(runtime, company_id)

    @router.post("/company-relationships/{relationship_id}/decide")
    def decide_group_scope(
        request: Request,
        relationship_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        with runtime.session_factory() as session:
            relationship = session.get(CompanyRelationshipModel, relationship_id)
            if relationship is None:
                raise HTTPException(status_code=404, detail="Unknown company relationship.")
            company_id = relationship.subject_company_id
        try:
            decision = IdentityDecisionType(str(payload.get("decision")))
            runtime.intakes.decide_group_scope(
                relationship_id=relationship_id,
                decision=decision,
                actor=reviewer_identity(),
                reason=str(payload.get("reason") or ""),
            )
        except (ValueError, CompanyIntakeValidationError) as exc:
            raise domain_error(
                exc
                if isinstance(exc, CompanyIntakeValidationError)
                else CompanyIntakeValidationError("Unknown relationship decision.")
            ) from exc
        return company_view(runtime, company_id)

    @router.post("/company-identifiers/{identifier_id}/decide")
    def decide_identifier(
        request: Request,
        identifier_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        with runtime.session_factory() as session:
            identifier = session.get(CompanyIdentifierModel, identifier_id)
            if identifier is None:
                raise HTTPException(status_code=404, detail="Unknown company identifier.")
            company_id = identifier.company_id
        try:
            decision = IdentityDecisionType(str(payload.get("decision")))
        except ValueError as exc:
            raise domain_error(
                CompanyIntakeValidationError("Unknown identifier decision.")
            ) from exc
        try:
            runtime.intakes.decide_identifier(
                identifier_id=identifier_id,
                decision=decision,
                actor=reviewer_identity(),
                reason=str(payload.get("reason") or ""),
            )
        except CompanyIntakeValidationError as exc:
            raise domain_error(exc) from exc
        return company_view(runtime, company_id)

    @router.post("/company-domains/{domain_id}/decide")
    def decide_domain(
        request: Request,
        domain_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        with runtime.session_factory() as session:
            domain = session.get(CompanyDomainModel, domain_id)
            if domain is None:
                raise HTTPException(status_code=404, detail="Unknown company domain.")
            company_id = domain.company_id
        try:
            decision = IdentityDecisionType(str(payload.get("decision")))
        except ValueError as exc:
            raise domain_error(CompanyIntakeValidationError("Unknown domain decision.")) from exc
        try:
            runtime.intakes.decide_domain(
                domain_id=domain_id,
                decision=decision,
                actor=reviewer_identity(),
                reason=str(payload.get("reason") or ""),
            )
        except CompanyIntakeValidationError as exc:
            raise domain_error(exc) from exc
        return company_view(runtime, company_id)

    @router.post("/research-cases/{research_case_id}/runs", status_code=201)
    def start_run(
        request: Request,
        research_case_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        service = research_service()
        cutoff = reporting_cutoff(payload)
        try:
            run = service.start(research_case_id, actor=reviewer_identity(), cutoff=cutoff)
        except CompanyResearchError as exc:
            raise domain_error(exc) from exc
        return run_view(runtime, run.id)

    @router.post("/research-runs/{run_id}/restart", status_code=201)
    def restart_run(
        request: Request,
        run_id: str,
        payload: Annotated[JsonDict | None, Body()] = None,
    ) -> JsonDict:
        body = payload or {}
        require_csrf(request, str(body.get("csrf_token") or "") or None)
        try:
            run = research_service().restart(
                run_id,
                actor=reviewer_identity(),
                cutoff=reporting_cutoff(body),
            )
        except CompanyResearchError as exc:
            raise domain_error(exc) from exc
        return run_view(runtime, run.id)

    @router.post("/research-runs/{run_id}/advance")
    def advance_run(
        request: Request,
        run_id: str,
        payload: Annotated[JsonDict | None, Body()] = None,
    ) -> JsonDict:
        body = payload or {}
        require_csrf(request, str(body.get("csrf_token") or "") or None)
        service = research_service()
        started = datetime.now(UTC)
        try:
            result = service.advance(run_id)
        except Exception as exc:
            state = run_view(runtime, run_id)
            state["advance"] = _advance_failure_payload(
                state,
                exc,
                elapsed_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
            )
            return state
        state = run_view(runtime, run_id)
        state["advance"] = {
            "ok": True,
            "capability": result.capability,
            "code": None,
            "message": None,
            "elapsed_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
            "retryable": False,
            "attempts_remaining": 0,
        }
        return state

    @router.post("/research-runs/{run_id}/cancel")
    def cancel_run(
        request: Request,
        run_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        service = research_service()
        try:
            service.cancel(
                run_id,
                actor=reviewer_identity(),
                reason=str(payload.get("reason") or ""),
            )
        except CompanyResearchError as exc:
            raise domain_error(exc) from exc
        return run_view(runtime, run_id)

    @router.post("/research-runs/{run_id}/recover")
    def recover_run(
        request: Request,
        run_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        service = research_service()
        try:
            service.recover_interrupted(
                run_id,
                actor=reviewer_identity(),
                reason=str(payload.get("reason") or ""),
            )
        except CompanyResearchError as exc:
            raise domain_error(exc) from exc
        return run_view(runtime, run_id)

    @router.post("/profile-versions/{profile_id}/decide")
    def decide_profile(
        request: Request,
        profile_id: str,
        payload: Annotated[JsonDict, Body()],
    ) -> JsonDict:
        require_csrf(request, str(payload.get("csrf_token") or "") or None)
        service = research_service()
        decision = str(payload.get("decision") or "")
        if decision not in {"approve", "reject"}:
            raise domain_error(CompanyResearchError("Unknown profile decision."))
        try:
            expected_lock_version = int(payload.get("expected_lock_version", 0))
        except (TypeError, ValueError) as exc:
            raise domain_error(
                CompanyResearchError("A numeric expected lock version is required.")
            ) from exc
        with runtime.session_factory() as session:
            profile = session.get(ProfileVersionModel, profile_id)
            if profile is None:
                raise HTTPException(status_code=404, detail="Unknown profile version.")
            run_id = profile.research_run_id
        try:
            service.review_profile(
                profile_id,
                approve=decision == "approve",
                actor=reviewer_identity(),
                reason=str(payload.get("reason") or ""),
                expected_lock_version=expected_lock_version,
            )
        except CompanyResearchError as exc:
            raise domain_error(exc) from exc
        if run_id is None:
            raise HTTPException(status_code=404, detail="Profile version has no research run.")
        return run_view(runtime, run_id)

    return router
