from __future__ import annotations

from portfolio_agent.cbit_contract import (
    ADMITTED_PUBLIC_SOURCES,
    CBIT_PROFILE_KEY,
    CBIT_ROWS,
    CBIT_ROWS_BY_LABEL,
    CBIT_ROWS_BY_NUMBER,
    CbitRowRole,
    CbitValueShape,
    PeriodSemantics,
    canonicalize_label,
    detect_cbit_profile,
    validate_contract,
)

EXPECTED_RETAINED_ROWS = {
    1,
    2,
    3,
    4,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    36,
    37,
    38,
    39,
    40,
    41,
    42,
    43,
    44,
    45,
    46,
    48,
    49,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    58,
    59,
    60,
    61,
    62,
    63,
    64,
    65,
    66,
    67,
    68,
    69,
    70,
    71,
    73,
    74,
    75,
    76,
    77,
    78,
    80,
    81,
    82,
    84,
    85,
    87,
    88,
    89,
    90,
    91,
    92,
    93,
    94,
    96,
    97,
    98,
    99,
    100,
    101,
    102,
}


def test_contract_enumerates_every_retained_workbook_label_once() -> None:
    validate_contract()
    assert {row.row_number for row in CBIT_ROWS} == EXPECTED_RETAINED_ROWS
    assert len(CBIT_ROWS_BY_NUMBER) == len(CBIT_ROWS)
    assert len(CBIT_ROWS_BY_LABEL) == len(CBIT_ROWS)


def test_held_rows_are_mixed_unresolved() -> None:
    held_shapes = {row.value_shape for row in CBIT_ROWS if row.role is CbitRowRole.HELD}
    assert held_shapes == {CbitValueShape.MIXED_UNRESOLVED}
    assert all(
        row.period_semantics is not PeriodSemantics.NONE
        for row in CBIT_ROWS
        if row.role is CbitRowRole.INPUT
    )


def test_profile_detection_requires_exact_version_sentinels() -> None:
    sentinels = {
        1: "Impact Questions",
        3: "Company House Name and Number",
        18: "Valuation X - %",
        49: "Total of Public Funding Secured",
        101: (
            "Estimated monthly or quarterly savings (£/% decrease in operational costs) "
            "attributed directly by AI"
        ),
    }
    assert detect_cbit_profile(sentinels)
    assert CBIT_PROFILE_KEY == "cbit-portfolio-metrics-q2-2025"

    sentinels[49] = "Private Funding Total"
    assert not detect_cbit_profile(sentinels)


def test_narratives_have_existing_parent_concepts() -> None:
    input_keys = {row.metric_key for row in CBIT_ROWS if row.role is CbitRowRole.INPUT}
    approved_held_parent_keys = {
        "research_development_spend_held",
        "customers_or_deals_held",
        "revenue_increase_held",
        "ai_tasks_per_employee_held",
        "ai_core_process_coverage_held",
        "ai_savings_held",
    }
    for row in CBIT_ROWS:
        if row.role is CbitRowRole.NARRATIVE:
            assert row.narrative_for in input_keys | approved_held_parent_keys


def test_admitted_sources_are_public_exact_id_and_non_inferential() -> None:
    assert {source.key for source in ADMITTED_PUBLIC_SOURCES} == {
        "companies_house",
        "ukri_gtr",
    }
    for source in ADMITTED_PUBLIC_SOURCES:
        assert source.public_only
        assert source.identifier_scheme
        assert "infer" in source.boundary.lower() or "causation" in source.boundary.lower()


def test_contract_canonicalisation_does_not_collapse_distinct_labels() -> None:
    assert canonicalize_label("R&D") == "r d"
    assert canonicalize_label("Number of Jobs Created") != canonicalize_label("Awards Received")
