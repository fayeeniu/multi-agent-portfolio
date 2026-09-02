"""Versioned contract for the supplied CBIT Q2 2025 workbook shape.

The contract describes structure only. It intentionally contains no portfolio-company
names or submitted values, so it is safe to keep in source control.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .enums import Sourceability

CBIT_PROFILE_KEY = "cbit-portfolio-metrics-q2-2025"
CBIT_CONTRACT_VERSION = "2026-08-26.2"


def canonicalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


class CbitRowRole(StrEnum):
    SECTION = "section"
    IDENTITY = "identity"
    JOIN_PERIOD = "join_period"
    INPUT = "input"
    NARRATIVE = "narrative"
    DERIVED = "derived"
    HELD = "held"


class CbitValueShape(StrEnum):
    INTEGER = "integer"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    ORDINAL = "ordinal"
    REPORTED_DURATION = "reported_duration"
    TEXT = "text"
    LIST = "list"
    IDENTITY = "identity"
    PERIOD = "period"
    MIXED_UNRESOLVED = "mixed_unresolved"
    FORMULA = "formula"
    NONE = "none"


class PeriodSemantics(StrEnum):
    REPORTING_PERIOD = "reporting_period"
    LAST_QUARTER = "last_quarter"
    AS_AT_CUTOFF = "as_at_reporting_cutoff"
    SINCE_PROGRAMME_START = "since_programme_start"
    BEFORE_PROGRAMME = "before_programme"
    LIFETIME = "lifetime_or_unspecified"
    EXPLANATORY = "explanatory_only"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class CbitRowDefinition:
    row_number: int
    label: str
    category: str
    role: CbitRowRole
    value_shape: CbitValueShape
    period_semantics: PeriodSemantics = PeriodSemantics.NONE
    sourceability: Sourceability | None = None
    metric_key: str | None = None
    unit: str | None = None
    narrative_for: str | None = None
    rationale: str | None = None

    @property
    def canonical_label(self) -> str:
        return canonicalize_label(self.label)

    @property
    def is_canonical_input(self) -> bool:
        return self.role is CbitRowRole.INPUT


@dataclass(frozen=True, slots=True)
class AdmittedSourceDefinition:
    key: str
    publisher: str
    title: str
    identifier_scheme: str
    permitted_uses: tuple[str, ...]
    retrieval_modes: tuple[str, ...]
    public_only: bool
    admission_version: str
    boundary: str


def _section(row: int, label: str, category: str) -> CbitRowDefinition:
    return CbitRowDefinition(
        row_number=row,
        label=label,
        category=category,
        role=CbitRowRole.SECTION,
        value_shape=CbitValueShape.NONE,
    )


def _input(
    row: int,
    label: str,
    category: str,
    key: str,
    shape: CbitValueShape,
    unit: str | None,
    period: PeriodSemantics,
    sourceability: Sourceability,
) -> CbitRowDefinition:
    return CbitRowDefinition(
        row_number=row,
        label=label,
        category=category,
        role=CbitRowRole.INPUT,
        value_shape=shape,
        period_semantics=period,
        sourceability=sourceability,
        metric_key=key,
        unit=unit,
    )


def _narrative(
    row: int,
    label: str,
    category: str,
    narrative_for: str,
) -> CbitRowDefinition:
    return CbitRowDefinition(
        row_number=row,
        label=label,
        category=category,
        role=CbitRowRole.NARRATIVE,
        value_shape=CbitValueShape.TEXT,
        period_semantics=PeriodSemantics.EXPLANATORY,
        sourceability=Sourceability.INTERNAL_ONLY,
        narrative_for=narrative_for,
    )


def _held(
    row: int,
    label: str,
    category: str,
    rationale: str,
) -> CbitRowDefinition:
    return CbitRowDefinition(
        row_number=row,
        label=label,
        category=category,
        role=CbitRowRole.HELD,
        value_shape=CbitValueShape.MIXED_UNRESOLVED,
        sourceability=Sourceability.INTERNAL_ONLY,
        rationale=rationale,
    )


CBIT_ROWS: tuple[CbitRowDefinition, ...] = (
    _section(1, "Impact Questions", "Workbook"),
    _section(2, "General Information", "General information"),
    CbitRowDefinition(
        3,
        "Company House Name and Number",
        "General information",
        CbitRowRole.IDENTITY,
        CbitValueShape.IDENTITY,
        sourceability=Sourceability.PUBLICLY_SOURCEABLE,
        rationale="Parsed only as an identity candidate; exact identifiers require review.",
    ),
    CbitRowDefinition(
        4,
        "Year and Quarter joined",
        "General information",
        CbitRowRole.JOIN_PERIOD,
        CbitValueShape.PERIOD,
        period_semantics=PeriodSemantics.SINCE_PROGRAMME_START,
        sourceability=Sourceability.INTERNAL_ONLY,
    ),
    _section(6, "Employment and Economic Impact", "Employment and economic impact"),
    _input(
        7,
        "Number of Successful Pivots",
        "Employment and economic impact",
        "successful_pivots",
        CbitValueShape.INTEGER,
        "pivots",
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(8, "Explanation for row 7", "Employment and economic impact", "successful_pivots"),
    _input(
        9,
        "For each successful pivot, could you briefly explain what prompted the change, what "
        "specific adjustments you made, and why you consider it successful?",
        "Employment and economic impact",
        "successful_pivot_details",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.INTERNAL_ONLY,
    ),
    _input(
        10,
        "How many jobs you would have lost? (Number of Jobs Safeguarded)",
        "Employment and economic impact",
        "jobs_safeguarded",
        CbitValueShape.INTEGER,
        "people",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(11, "Explanation for row 10", "Employment and economic impact", "jobs_safeguarded"),
    _input(
        12,
        "Number of Jobs Created",
        "Employment and economic impact",
        "jobs_created",
        CbitValueShape.INTEGER,
        "people",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(13, "Explanation for row 12", "Employment and economic impact", "jobs_created"),
    _input(
        14,
        "Estimated Current Valuation",
        "Employment and economic impact",
        "valuation",
        CbitValueShape.CURRENCY,
        "currency_units",
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(15, "Explanation for row 14", "Employment and economic impact", "valuation"),
    _input(
        16,
        "Estimated Valuation before VB",
        "Employment and economic impact",
        "valuation_before_programme",
        CbitValueShape.CURRENCY,
        "currency_units",
        PeriodSemantics.BEFORE_PROGRAMME,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(
        17,
        "Explanation for row 16",
        "Employment and economic impact",
        "valuation_before_programme",
    ),
    CbitRowDefinition(
        18,
        "Valuation X - %",
        "Employment and economic impact",
        CbitRowRole.DERIVED,
        CbitValueShape.FORMULA,
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.DERIVED,
        rationale="Workbook formula/aggregate; recompute only from admitted inputs.",
    ),
    _section(20, "Research and Development (R&D)", "Research and development"),
    _held(
        21,
        "Total or % of Revenue spent on R&D",
        "Research and development",
        "Total currency and percentage-of-revenue are different measures and cannot be guessed.",
    ),
    _narrative(
        22,
        "Explanation for row 20",
        "Research and development",
        "research_development_spend_held",
    ),
    _input(
        23,
        "Number of Innovations Developed",
        "Research and development",
        "innovations_developed",
        CbitValueShape.INTEGER,
        "innovations",
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.MIXED,
    ),
    _narrative(
        24,
        "Explanation for row 22",
        "Research and development",
        "innovations_developed",
    ),
    _input(
        25,
        "Number of Innovations in Development (Number of Product/Services Scoped/In "
        "development) - move to Products section",
        "Research and development",
        "innovations_in_development",
        CbitValueShape.INTEGER,
        "innovations",
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.MIXED,
    ),
    _narrative(
        26,
        "Explanation for row 24",
        "Research and development",
        "innovations_in_development",
    ),
    _input(
        27,
        "Patents Pending",
        "Research and development",
        "patents_pending",
        CbitValueShape.INTEGER,
        "patents",
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.MIXED,
    ),
    _narrative(28, "Explanation for row 26", "Research and development", "patents_pending"),
    _input(
        29,
        "Patents Secured",
        "Research and development",
        "patents_secured",
        CbitValueShape.INTEGER,
        "patents",
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.MIXED,
    ),
    _narrative(30, "Explanation for row 28", "Research and development", "patents_secured"),
    _section(31, "Technology Readiness Level (TRL) Progression", "Technology readiness"),
    _input(
        32,
        "Current TRL Level",
        "Technology readiness",
        "technology_readiness_level",
        CbitValueShape.ORDINAL,
        "trl_level",
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.MIXED,
    ),
    _narrative(
        33,
        "What enabled progression from TRL (x-1) to (x)?",
        "Technology readiness",
        "technology_readiness_level",
    ),
    _input(
        34,
        "Has a VB programme elements supported TRL progression? If Yes, which one?",
        "Technology readiness",
        "programme_support_for_trl",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.INTERNAL_ONLY,
    ),
    _section(36, "Products and Processes", "Products and processes"),
    _input(
        37,
        "Number of Product Launches",
        "Products and processes",
        "products_launched",
        CbitValueShape.INTEGER,
        "products",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.MIXED,
    ),
    _narrative(38, "Explanation for row 36", "Products and processes", "products_launched"),
    _input(
        39,
        "Number of New Products Launched (including how many recycled: source code, value "
        "proposition, software versions)",
        "Products and processes",
        "new_and_recycled_products_launched",
        CbitValueShape.INTEGER,
        "products",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.MIXED,
    ),
    _narrative(
        40,
        "Explanation for row 38",
        "Products and processes",
        "new_and_recycled_products_launched",
    ),
    _input(
        41,
        "Time from Idea to Deployment",
        "Products and processes",
        "idea_to_deployment_reported",
        CbitValueShape.REPORTED_DURATION,
        "reported_duration",
        PeriodSemantics.LIFETIME,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(
        42,
        "Explanation for row 40",
        "Products and processes",
        "idea_to_deployment_reported",
    ),
    _input(
        43,
        "Number of Products Failed",
        "Products and processes",
        "products_failed",
        CbitValueShape.INTEGER,
        "products",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(44, "Explanation for row 42", "Products and processes", "products_failed"),
    _input(
        45,
        "Estimated % Process Efficiency Improvements",
        "Products and processes",
        "process_efficiency_improvement",
        CbitValueShape.PERCENTAGE,
        "percentage_points",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(
        46,
        "Explanation for row 44",
        "Products and processes",
        "process_efficiency_improvement",
    ),
    _section(48, "Funding and Investments", "Funding and investments"),
    _input(
        49,
        "Total of Public Funding Secured",
        "Funding and investments",
        "grant_funding",
        CbitValueShape.CURRENCY,
        "currency_units",
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.MIXED,
    ),
    _narrative(
        50,
        "List of Public Funding Secured (amount and details)",
        "Funding and investments",
        "grant_funding",
    ),
    _input(
        51,
        "Total of Private Funding Secured",
        "Funding and investments",
        "private_funding",
        CbitValueShape.CURRENCY,
        "currency_units",
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(
        52,
        "List of Private Funding Secured (amount and source)",
        "Funding and investments",
        "private_funding",
    ),
    _input(
        53,
        "New Investment in Capital Equipment (CAPEX) from the start of the year",
        "Funding and investments",
        "capital_expenditure_since_start",
        CbitValueShape.CURRENCY,
        "currency_units",
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(
        54,
        "Explanation for row 52",
        "Funding and investments",
        "capital_expenditure_since_start",
    ),
    _input(
        55,
        "New Investment in Operational Equipment (OPEX) from the start of the year",
        "Funding and investments",
        "operating_expenditure_since_start",
        CbitValueShape.CURRENCY,
        "currency_units",
        PeriodSemantics.SINCE_PROGRAMME_START,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(
        56,
        "Explanation for row 54",
        "Funding and investments",
        "operating_expenditure_since_start",
    ),
    _section(58, "Market and Partnerships", "Market and partnerships"),
    _held(
        59,
        "Number of Customers/Deals Secured last quarter",
        "Market and partnerships",
        "Customers and deals are different countable entities and must be split at collection.",
    ),
    _narrative(
        60,
        "Explanation for row 58",
        "Market and partnerships",
        "customers_or_deals_held",
    ),
    _input(
        61,
        "Number of Industry Awards and Recognitions",
        "Market and partnerships",
        "awards_received",
        CbitValueShape.INTEGER,
        "awards",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.PUBLICLY_SOURCEABLE,
    ),
    _narrative(62, "Explanation for row 60", "Market and partnerships", "awards_received"),
    _input(
        63,
        "Number of Collaborations with Research Institutions",
        "Market and partnerships",
        "research_collaborations_reported",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.MIXED,
    ),
    _narrative(
        64,
        "Explanation for row 62",
        "Market and partnerships",
        "research_collaborations_reported",
    ),
    _input(
        65,
        "Publication Outlets (journals, university magazines, reports)",
        "Market and partnerships",
        "publication_outlets_reported",
        CbitValueShape.LIST,
        None,
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.PUBLICLY_SOURCEABLE,
    ),
    _narrative(
        66,
        "Explanation for row 64",
        "Market and partnerships",
        "publication_outlets_reported",
    ),
    _input(
        67,
        "Number of Guest Speaker Conferences and Keynotes",
        "Market and partnerships",
        "guest_conferences_reported",
        CbitValueShape.LIST,
        None,
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.PUBLICLY_SOURCEABLE,
    ),
    _narrative(
        68,
        "Explanation for row 66",
        "Market and partnerships",
        "guest_conferences_reported",
    ),
    _input(
        69,
        "New Industries Entered",
        "Market and partnerships",
        "new_industries_reported",
        CbitValueShape.LIST,
        None,
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.MIXED,
    ),
    _narrative(
        70,
        "Explanation for row 68",
        "Market and partnerships",
        "new_industries_reported",
    ),
    _input(
        71,
        "Adoption Rate of New Tech Suggested by VB Team",
        "Market and partnerships",
        "new_technology_adoption_rate",
        CbitValueShape.PERCENTAGE,
        "percentage_points",
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.INTERNAL_ONLY,
    ),
    _section(73, "Financial Impact", "Financial impact"),
    _held(
        74,
        "Estimated % or £ Revenue Increase",
        "Financial impact",
        "Absolute revenue increase and percentage revenue increase require separate fields.",
    ),
    _narrative(75, "Explanation for row 73", "Financial impact", "revenue_increase_held"),
    _input(
        76,
        "Estimated % Product Profit Margin",
        "Financial impact",
        "product_profit_margin",
        CbitValueShape.PERCENTAGE,
        "percentage_points",
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.INTERNAL_ONLY,
    ),
    _narrative(77, "Explanation for row 75", "Financial impact", "product_profit_margin"),
    _input(
        78,
        "Expansion Plans",
        "Financial impact",
        "expansion_plans_reported",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.INTERNAL_ONLY,
    ),
    _section(80, "Diversity and Sustainability", "Diversity and sustainability"),
    _input(
        81,
        "Contribution to SDGs",
        "Diversity and sustainability",
        "sustainable_development_goals_reported",
        CbitValueShape.LIST,
        None,
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.MIXED,
    ),
    _input(
        82,
        "Diversity and Inclusion Metrics",
        "Diversity and sustainability",
        "diversity_metrics_reported",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.INTERNAL_ONLY,
    ),
    _section(84, "Policy and Influence*", "Policy and influence"),
    _input(
        85,
        "Estimated Policy Influence Traction",
        "Policy and influence",
        "policy_traction_reported",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.MIXED,
    ),
    _section(87, "AI-powered Operational Efficiency", "AI operational efficiency"),
    _held(
        88,
        "Average time to complete key tasks before vs. after implementing AI",
        "AI operational efficiency",
        "Before and after durations require two values, units, and a comparable task definition.",
    ),
    _input(
        89,
        "What are the top 3 key tasks that were impacted?",
        "AI operational efficiency",
        "ai_top_tasks_reported",
        CbitValueShape.LIST,
        None,
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.INTERNAL_ONLY,
    ),
    _input(
        90,
        "Can you describe any changes in how your team works since introducing this?",
        "AI operational efficiency",
        "ai_team_changes_reported",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.INTERNAL_ONLY,
    ),
    _held(
        91,
        "Number (or %) of mistakes or errors per month before and after AI",
        "AI operational efficiency",
        "Count, rate, before, and after are separate measures with distinct denominators.",
    ),
    _input(
        92,
        "What are the top 3 occuring mistakes/scenarios that were impacted?",
        "AI operational efficiency",
        "ai_top_mistakes_reported",
        CbitValueShape.LIST,
        None,
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.INTERNAL_ONLY,
    ),
    _held(
        93,
        "Average number/% of completed tasks/projects per employee each month, before and after AI",
        "AI operational efficiency",
        "Tasks and projects plus absolute and percentage values require separate denominators.",
    ),
    _narrative(
        94,
        "Explanation for row 92",
        "AI operational efficiency",
        "ai_tasks_per_employee_held",
    ),
    _section(96, "AI Adoption & Readiness", "AI adoption and readiness"),
    _held(
        97,
        "Number (or %) of core processes successfully automated using AI",
        "AI adoption and readiness",
        "Absolute coverage and percentage coverage require separate denominator-aware fields.",
    ),
    _narrative(
        98,
        "Explanation for row 96",
        "AI adoption and readiness",
        "ai_core_process_coverage_held",
    ),
    _input(
        99,
        "What prompted you to automate these particular processes?",
        "AI adoption and readiness",
        "automation_rationale_reported",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.AS_AT_CUTOFF,
        Sourceability.INTERNAL_ONLY,
    ),
    _input(
        100,
        "AI-powered Business Performance",
        "AI adoption and readiness",
        "ai_business_performance_reported",
        CbitValueShape.TEXT,
        None,
        PeriodSemantics.REPORTING_PERIOD,
        Sourceability.INTERNAL_ONLY,
    ),
    _held(
        101,
        "Estimated monthly or quarterly savings (£/% decrease in operational costs) "
        "attributed directly by AI",
        "AI adoption and readiness",
        "Frequency, absolute amount, percentage, and attribution basis require separate fields.",
    ),
    _narrative(
        102,
        "What factors do you think contributed most to these savings?",
        "AI adoption and readiness",
        "ai_savings_held",
    ),
)

CBIT_ROWS_BY_NUMBER = {row.row_number: row for row in CBIT_ROWS}
CBIT_ROWS_BY_LABEL = {row.canonical_label: row for row in CBIT_ROWS}

CBIT_REQUIRED_SENTINELS: tuple[tuple[int, str], ...] = (
    (1, "Impact Questions"),
    (3, "Company House Name and Number"),
    (18, "Valuation X - %"),
    (49, "Total of Public Funding Secured"),
    (
        101,
        "Estimated monthly or quarterly savings (£/% decrease in operational costs) "
        "attributed directly by AI",
    ),
)

ADMITTED_PUBLIC_SOURCES: tuple[AdmittedSourceDefinition, ...] = (
    AdmittedSourceDefinition(
        key="companies_house",
        publisher="Companies House",
        title="Companies House public company register and filing data",
        identifier_scheme="companies_house_number",
        permitted_uses=(
            "exact company identity and status",
            "incorporation and dissolution events",
            "SIC and registered-office postcode context",
            "accounts and filing-period facts when explicitly published",
            "charges and public share-related events without inferred valuation",
        ),
        retrieval_modes=("offline_snapshot", "read_only_api"),
        public_only=True,
        admission_version="2026-08-26.1",
        boundary=(
            "No valuation, funding-round amount, dilution, recommendation, or causal impact may "
            "be inferred from register records."
        ),
    ),
    AdmittedSourceDefinition(
        key="ukri_gtr",
        publisher="UK Research and Innovation",
        title="UKRI Gateway to Research public project and award records",
        identifier_scheme="ukri_organisation_id",
        permitted_uses=(
            "opportunity, award, project, and outcome lifecycle events",
            "explicit award amount and currency",
            "funder and organisation roles",
            "public project dates and identifiers",
        ),
        retrieval_modes=("offline_snapshot",),
        public_only=True,
        admission_version="2026-08-26.1",
        boundary=(
            "Organisation association is descriptive evidence only and must not be phrased as "
            "programme causation."
        ),
    ),
)


def detect_cbit_profile(labels_by_row: dict[int, str]) -> bool:
    """Return true only when every version sentinel occurs at its exact row."""

    return all(
        canonicalize_label(labels_by_row.get(row_number, "")) == canonicalize_label(expected_label)
        for row_number, expected_label in CBIT_REQUIRED_SENTINELS
    )


def validate_contract() -> None:
    """Raise on structural ambiguity; called by tests and catalogue construction."""

    row_numbers = [row.row_number for row in CBIT_ROWS]
    labels = [row.canonical_label for row in CBIT_ROWS]
    if len(row_numbers) != len(set(row_numbers)):
        raise ValueError("CBIT contract contains duplicate row numbers.")
    if len(labels) != len(set(labels)):
        raise ValueError("CBIT contract contains duplicate labels after canonicalisation.")

    input_keys = {row.metric_key for row in CBIT_ROWS if row.role is CbitRowRole.INPUT}
    if None in input_keys:
        raise ValueError("Every canonical CBIT input requires a metric key.")
    for row in CBIT_ROWS:
        if row.role is CbitRowRole.NARRATIVE and row.narrative_for is None:
            raise ValueError(f"Narrative row {row.row_number} has no parent key.")
        if (
            row.role
            in {
                CbitRowRole.SECTION,
                CbitRowRole.DERIVED,
                CbitRowRole.HELD,
            }
            and row.metric_key is not None
        ):
            raise ValueError(f"Non-input row {row.row_number} exposes a metric key.")


validate_contract()
