"""CBIT metric coverage and evidence-bound investment report proposal.

The supplied Q2 2025 workbook is treated as a versioned metric catalogue, not as
an instruction source and not as permission to publish its submitted values.
Public research may populate only metrics marked public or mixed, and only when
an admitted claim uses the canonical metric key as its subject.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Protocol

from .cbit_contract import CBIT_CONTRACT_VERSION, CBIT_ROWS, CbitRowRole
from .enums import Sourceability


class MetricClaim(Protocol):
    id: str
    category: str
    subject_key: str
    statement: str
    evidence_span: str
    source_locator: str
    event_date: str | None
    amount: str | None
    currency: str | None
    perspective: str
    verification_status: str


HELD_METRIC_SPLITS: dict[int, tuple[str, ...]] = {
    21: ("research_development_spend_amount", "research_development_spend_percent_revenue"),
    59: ("customers_secured_count", "deals_secured_count"),
    74: ("revenue_increase_amount", "revenue_increase_percentage"),
    88: ("task_duration_before", "task_duration_after", "comparable_task_definition"),
    91: ("errors_before", "errors_after", "error_denominator"),
    93: (
        "tasks_per_employee_before",
        "tasks_per_employee_after",
        "projects_per_employee_before",
        "projects_per_employee_after",
    ),
    97: ("automated_process_count", "automated_process_percentage", "core_process_total"),
    101: (
        "ai_savings_amount",
        "ai_savings_percentage",
        "savings_period",
        "attribution_basis",
    ),
}

REPORT_SECTION_PROPOSAL: tuple[dict[str, Any], ...] = (
    {
        "key": "executive_evidence_summary",
        "heading": "Executive evidence summary",
        "purpose": "Decision context, evidence balance, contradictions and material gaps.",
        "categories": (),
    },
    {
        "key": "employment_and_economic_impact",
        "heading": "Employment and economic impact",
        "purpose": "Jobs, pivots and valuation inputs with explicit period semantics.",
        "categories": ("Employment and economic impact",),
    },
    {
        "key": "research_and_technology",
        "heading": "R&D, intellectual property and technology readiness",
        "purpose": "Innovation pipeline, patents and TRL evidence.",
        "categories": ("Research and development", "Technology readiness"),
    },
    {
        "key": "products_and_operations",
        "heading": "Products, delivery and operating efficiency",
        "purpose": "Launches, failures, delivery cycle and process efficiency.",
        "categories": ("Products and processes",),
    },
    {
        "key": "capital_and_financial_impact",
        "heading": "Funding, capital deployment and financial impact",
        "purpose": "Public/private funding, capex, opex, margin and expansion evidence.",
        "categories": ("Funding and investments", "Financial impact"),
    },
    {
        "key": "market_and_partnerships",
        "heading": "Market traction, partnerships and external recognition",
        "purpose": "Customers, collaborations, awards, publications and new markets.",
        "categories": ("Market and partnerships",),
    },
    {
        "key": "impact_and_policy",
        "heading": "Sustainability, diversity and policy influence",
        "purpose": "Attributed impact claims and independently sourceable policy traction.",
        "categories": ("Diversity and sustainability", "Policy and influence"),
    },
    {
        "key": "ai_readiness_and_efficiency",
        "heading": "AI adoption, operational efficiency and business performance",
        "purpose": "Before/after measures with denominators, attribution and evidence limits.",
        "categories": (
            "AI operational efficiency",
            "AI adoption and readiness",
        ),
    },
    {
        "key": "risk_and_diligence_gaps",
        "heading": "Risks, contradictions and diligence requests",
        "purpose": "Adverse evidence, unresolved conflicts and the next documents required.",
        "categories": (),
    },
    {
        "key": "source_and_methodology_appendix",
        "heading": "Sources, methodology and provenance appendix",
        "purpose": "Exact spans, source locators, cut-off, model route and review record.",
        "categories": (),
    },
)

# Claims in these research categories are useful context for a CBIT section even
# when they do not satisfy a metric's exact key, value shape, or period semantics.
# They are surfaced as public signals and never promoted to metric evidence.
CATEGORY_SIGNAL_CLAIMS: dict[str, tuple[str, ...]] = {
    "Employment and economic impact": ("performance",),
    "Research and development": ("technology", "awards"),
    "Technology readiness": ("technology",),
    "Products and processes": ("products_market", "technology"),
    "Funding and investments": ("funding", "corporate_actions"),
    "Market and partnerships": ("awards", "products_market", "public_discourse"),
    "Financial impact": ("performance", "corporate_actions"),
    "Diversity and sustainability": ("public_discourse",),
    "Policy and influence": ("regulation", "public_discourse"),
    "AI operational efficiency": ("performance", "technology"),
    "AI adoption and readiness": ("technology", "products_market"),
}

REPORT_SECTION_CLAIM_CATEGORIES: dict[str, tuple[str, ...]] = {
    "executive_evidence_summary": ("identity", "other"),
    "employment_and_economic_impact": ("performance",),
    "research_and_technology": ("technology", "awards"),
    "products_and_operations": ("products_market",),
    "capital_and_financial_impact": ("funding", "corporate_actions", "performance"),
    "market_and_partnerships": ("awards", "products_market", "public_discourse"),
    "impact_and_policy": ("regulation", "public_discourse"),
    "ai_readiness_and_efficiency": ("technology", "performance"),
    "risk_and_diligence_gaps": ("challenges", "regulation", "public_discourse"),
    "source_and_methodology_appendix": (),
}


def public_research_metric_keys() -> frozenset[str]:
    return frozenset(
        row.metric_key
        for row in CBIT_ROWS
        if row.role is CbitRowRole.INPUT
        and row.metric_key is not None
        and row.sourceability in {Sourceability.PUBLICLY_SOURCEABLE, Sourceability.MIXED}
    )


PUBLIC_RESEARCH_METRIC_KEYS = public_research_metric_keys()


def public_metric_prompt_roster() -> str:
    """Return the bounded canonical metric vocabulary for model extraction."""

    rows = [
        f"- {row.metric_key}: {row.label} "
        f"[type={row.value_shape.value}; unit={row.unit or 'no fixed unit'}; "
        f"period={row.period_semantics.value}; "
        f"boundary={row.sourceability.value if row.sourceability else 'unspecified'}]"
        for row in CBIT_ROWS
        if row.role is CbitRowRole.INPUT and row.metric_key in PUBLIC_RESEARCH_METRIC_KEYS
    ]
    return "\n".join(rows)


def _claim_payload(claim: MetricClaim) -> dict[str, Any]:
    return {
        "claim_id": claim.id,
        "statement": claim.statement,
        "evidence_span": claim.evidence_span,
        "source_url": claim.source_locator,
        "event_date": claim.event_date,
        "reported_value": claim.amount,
        "currency": claim.currency,
        "perspective": claim.perspective,
        "verification_status": claim.verification_status,
    }


def build_investment_report(
    claims: Iterable[MetricClaim], *, entity_scope: str = "legal_entity"
) -> dict[str, Any]:
    """Build a deterministic metric ledger and report outline from admitted claims."""

    claim_rows = [
        claim
        for claim in claims
        if getattr(claim, "entity_scope", "legal_entity") == entity_scope
    ]
    claims_by_metric: defaultdict[str, list[MetricClaim]] = defaultdict(list)
    for claim in claim_rows:
        if claim.subject_key in PUBLIC_RESEARCH_METRIC_KEYS:
            claims_by_metric[claim.subject_key].append(claim)

    def supporting_claims(category: str) -> list[MetricClaim]:
        admitted_categories = CATEGORY_SIGNAL_CLAIMS.get(category, ())
        return [
            claim
            for claim in claim_rows
            if claim.category in admitted_categories
            and claim.subject_key not in PUBLIC_RESEARCH_METRIC_KEYS
        ]

    categories: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    populated = 0
    publicly_evidenced = 0
    internally_evidenced = 0
    document_required = 0
    not_found_publicly = 0
    for row in CBIT_ROWS:
        if row.role is not CbitRowRole.INPUT or row.metric_key is None:
            continue
        metric_claims = claims_by_metric.get(row.metric_key, [])
        if metric_claims:
            has_internal = any(
                claim.perspective == "internal_document" for claim in metric_claims
            )
            has_public = any(
                claim.perspective != "internal_document" for claim in metric_claims
            )
            status = (
                "hybrid_evidence"
                if has_internal and has_public
                else "internal_document_evidence"
                if has_internal
                else "public_evidence"
            )
            populated += 1
            publicly_evidenced += int(has_public)
            internally_evidenced += int(has_internal)
        elif row.sourceability is Sourceability.INTERNAL_ONLY:
            status = "document_required"
            document_required += 1
        else:
            status = "not_found_publicly"
            not_found_publicly += 1
        categories[row.category].append(
            {
                "key": row.metric_key,
                "label": row.label,
                "data_type": row.value_shape.value,
                "unit": row.unit,
                "period_semantics": row.period_semantics.value,
                "sourceability": row.sourceability.value if row.sourceability else None,
                "status": status,
                "evidence": [_claim_payload(claim) for claim in metric_claims],
            }
        )

    held_questions = [
        {
            "row": row.row_number,
            "label": row.label,
            "category": row.category,
            "status": "definition_required",
            "required_fields": list(HELD_METRIC_SPLITS[row.row_number]),
            "reason": row.rationale,
        }
        for row in CBIT_ROWS
        if row.role is CbitRowRole.HELD
    ]
    derived_metrics = [
        {
            "key": "valuation_change_percentage",
            "label": "Valuation change since joining programme",
            "status": "inputs_required",
            "formula": (
                "(current valuation - valuation before programme) / valuation before programme"
            ),
            "required_metrics": ["valuation", "valuation_before_programme"],
        }
    ]
    metric_count = sum(len(rows) for rows in categories.values())
    public_metric_count = len(PUBLIC_RESEARCH_METRIC_KEYS)
    public_signal_claims = [
        claim for claim in claim_rows if claim.subject_key not in PUBLIC_RESEARCH_METRIC_KEYS
    ]
    source_count = len({claim.source_locator for claim in claim_rows})
    category_payloads = []
    for key, rows in categories.items():
        signals = supporting_claims(key)
        category_payloads.append(
            {
                "key": key,
                "metrics": rows,
                "supporting_public_evidence": [_claim_payload(claim) for claim in signals],
                "supporting_public_evidence_count": len(signals),
            }
        )

    report_sections = []
    for section in REPORT_SECTION_PROPOSAL:
        claim_categories = REPORT_SECTION_CLAIM_CATEGORIES[section["key"]]
        evidence = [claim for claim in claim_rows if claim.category in claim_categories]
        report_sections.append(
            {
                **section,
                "categories": list(section["categories"]),
                "claim_categories": list(claim_categories),
                "evidence_count": len(evidence),
                "evidence": [_claim_payload(claim) for claim in evidence],
            }
        )
    return {
        "schema_version": "cbit-investment-report-proposal-v2",
        "entity_scope": entity_scope,
        "metric_contract_version": CBIT_CONTRACT_VERSION,
        "summary": {
            "defined_metrics": metric_count,
            "publicly_sourceable_metrics": public_metric_count,
            "evidenced": populated,
            "publicly_evidenced": publicly_evidenced,
            "internally_evidenced": internally_evidenced,
            "public_metric_coverage_percent": round(
                (populated / public_metric_count) * 100 if public_metric_count else 0
            ),
            "supporting_public_signals": len(public_signal_claims),
            "evidence_sources": source_count,
            "document_required": document_required,
            "not_found_publicly": not_found_publicly,
            "definition_required": len(held_questions),
            "derived_metrics": len(derived_metrics),
            "unmapped_claims": sum(
                claim.subject_key not in PUBLIC_RESEARCH_METRIC_KEYS for claim in claim_rows
            ),
        },
        "categories": category_payloads,
        "held_questions": held_questions,
        "derived_metrics": derived_metrics,
        "report_sections": report_sections,
        "decision_boundary": (
            "Metric coverage organises diligence evidence; it is not a valuation, forecast, "
            "investment score or recommendation."
        ),
    }
