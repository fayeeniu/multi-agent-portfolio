from __future__ import annotations

from dataclasses import dataclass

from portfolio_agent.investment_metrics import (
    HELD_METRIC_SPLITS,
    PUBLIC_RESEARCH_METRIC_KEYS,
    build_investment_report,
    public_metric_prompt_roster,
)


@dataclass(frozen=True)
class _Claim:
    id: str
    category: str
    subject_key: str
    statement: str
    evidence_span: str
    source_locator: str
    event_date: str | None = None
    amount: str | None = None
    currency: str | None = None
    perspective: str = "fact"
    verification_status: str = "verbatim_exact_span"


def test_metric_report_populates_only_canonical_public_or_mixed_metric_keys() -> None:
    grant = _Claim(
        id="claim-grant",
        category="awards",
        subject_key="grant_funding",
        statement="The public award record states that GBP 412000 was awarded for the project.",
        evidence_span=(
            "The public award record states that GBP 412000 was awarded for the project."
        ),
        source_locator="https://gtr.ukri.org/projects/example",
        amount="412000",
        currency="GBP",
    )
    unrelated = _Claim(
        id="claim-other",
        category="technology",
        subject_key="platform_stack",
        statement="The company publishes technical documentation for its hosted platform.",
        evidence_span="The company publishes technical documentation for its hosted platform.",
        source_locator="https://example.com/technology",
    )

    report = build_investment_report([grant, unrelated])

    assert report["summary"] == {
        "defined_metrics": 37,
        "publicly_sourceable_metrics": 15,
        "evidenced": 1,
        "publicly_evidenced": 1,
        "internally_evidenced": 0,
        "public_metric_coverage_percent": 7,
        "supporting_public_signals": 1,
        "evidence_sources": 2,
        "document_required": 22,
        "not_found_publicly": 14,
        "definition_required": 8,
        "derived_metrics": 1,
        "unmapped_claims": 1,
    }
    metrics = {
        metric["key"]: metric
        for category in report["categories"]
        for metric in category["metrics"]
    }
    assert metrics["grant_funding"]["status"] == "public_evidence"
    assert metrics["grant_funding"]["evidence"][0]["reported_value"] == "412000"
    assert metrics["private_funding"]["status"] == "document_required"
    assert metrics["awards_received"]["status"] == "not_found_publicly"
    research = next(
        category
        for category in report["categories"]
        if category["key"] == "Research and development"
    )
    assert research["supporting_public_evidence_count"] == 1
    assert research["supporting_public_evidence"][0]["claim_id"] == "claim-other"
    research_section = next(
        section
        for section in report["report_sections"]
        if section["key"] == "research_and_technology"
    )
    assert research_section["evidence_count"] == 2
    assert len(report["report_sections"]) == 10


def test_ambiguous_workbook_questions_remain_split_and_unpopulated() -> None:
    report = build_investment_report([])

    assert set(HELD_METRIC_SPLITS) == {21, 59, 74, 88, 91, 93, 97, 101}
    assert {item["row"] for item in report["held_questions"]} == set(HELD_METRIC_SPLITS)
    assert all(item["status"] == "definition_required" for item in report["held_questions"])
    assert report["derived_metrics"][0]["status"] == "inputs_required"


def test_public_metric_prompt_excludes_internal_only_metrics() -> None:
    roster = public_metric_prompt_roster()

    assert "grant_funding" in PUBLIC_RESEARCH_METRIC_KEYS
    assert "grant_funding" in roster
    assert "period=since_programme_start" in roster
    assert "boundary=mixed" in roster
    assert "private_funding" not in PUBLIC_RESEARCH_METRIC_KEYS
    assert "private_funding" not in roster
