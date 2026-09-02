"""Unit tests for the offline research adapters.

The point of these adapters is that they replay recorded material without
weakening any control. These tests pin the recorded outcomes and confirm the
adapters never reach the network or invent a URL.
"""

from __future__ import annotations

from datetime import date

import pytest

from portfolio_agent.bootstrap import project_root
from portfolio_agent.company_research import CompanyResearchError, visible_text
from portfolio_agent.company_research_fixtures import (
    FIXTURE_MODEL_NAME,
    FixturePublicFetcher,
    FixtureResearchCorpus,
    FixtureResearchModel,
    load_fixture_pages,
)

CUTOFF = date(2026, 8, 27)
NUMBER = "09339981"
NAME = "Unresolved company (CH 09339981)"


def _corpus() -> FixtureResearchCorpus:
    return FixtureResearchCorpus(
        load_fixture_pages(project_root() / "fixtures" / "company_research_demo.json")
    )


def test_discovery_fills_templates_and_records_only_urls() -> None:
    model = FixtureResearchModel(_corpus())
    result = model.discover(
        company_number=NUMBER,
        company_name=NAME,
        cutoff=CUTOFF,
        max_sources=12,
        max_tool_calls=12,
        max_output_tokens=5_000,
    )
    urls = [item.url for item in result.sources]
    assert result.model == FIXTURE_MODEL_NAME
    assert result.tool_calls == 0
    assert all(url.startswith("https://") for url in urls)
    assert f"https://find-and-update.company-information.service.gov.uk/company/{NUMBER}" in urls
    # The host slug is keyed on the exact identifier, never on the placeholder name.
    assert any(f"company-{NUMBER}" in url for url in urls)
    assert not any("unresolved" in url for url in urls)


def test_discovery_respects_the_pinned_source_budget() -> None:
    model = FixtureResearchModel(_corpus())
    result = model.discover(
        company_number=NUMBER,
        company_name=NAME,
        cutoff=CUTOFF,
        max_sources=2,
        max_tool_calls=12,
        max_output_tokens=5_000,
    )
    assert len(result.sources) == 2


def test_recorded_outcomes_surface_as_the_real_failure_codes() -> None:
    corpus = _corpus()
    model = FixtureResearchModel(corpus)
    model.discover(
        company_number=NUMBER,
        company_name=NAME,
        cutoff=CUTOFF,
        max_sources=12,
        max_tool_calls=12,
        max_output_tokens=5_000,
    )
    fetcher = FixturePublicFetcher(corpus)

    page = fetcher.fetch(
        f"https://find-and-update.company-information.service.gov.uk/company/{NUMBER}"
    )
    assert page.status_code == 200
    assert page.media_type == "text/html"
    assert NUMBER in visible_text(page.content, page.media_type)

    for url, code in (
        (f"https://www.paywalledreview.example/company-{NUMBER}", "robots_blocked"),
        (f"https://cdn.filings.example/company-{NUMBER}/annual-report.pdf", "unsupported_media"),
        (f"https://www.regionalbusinesswire.example/company-{NUMBER}/update", "fetch_failed"),
    ):
        with pytest.raises(CompanyResearchError) as failure:
            fetcher.fetch(url)
        assert failure.value.code == code


def test_an_unrecorded_url_is_never_invented() -> None:
    fetcher = FixturePublicFetcher(_corpus())
    with pytest.raises(CompanyResearchError) as failure:
        fetcher.fetch("https://www.example.org/not-in-the-fixture")
    assert failure.value.code == "http_404"


def test_extraction_proposes_only_verbatim_spans_of_the_supplied_text() -> None:
    corpus = _corpus()
    model = FixtureResearchModel(corpus)
    discovery = model.discover(
        company_number=NUMBER,
        company_name=NAME,
        cutoff=CUTOFF,
        max_sources=12,
        max_tool_calls=12,
        max_output_tokens=5_000,
    )
    fetcher = FixturePublicFetcher(corpus)
    sources: list[dict[str, str]] = []
    for item in discovery.sources:
        try:
            page = fetcher.fetch(item.url)
        except CompanyResearchError:
            continue
        sources.append(
            {
                "url": item.url,
                "title": item.title or "",
                "text": visible_text(page.content, page.media_type),
            }
        )

    envelope, telemetry = model.extract(
        company_number=NUMBER,
        company_name=NAME,
        cutoff=CUTOFF,
        sources=sources,
        max_output_tokens=5_000,
    )
    assert telemetry.model == FIXTURE_MODEL_NAME
    assert envelope.claims
    by_url = {source["url"]: source["text"] for source in sources}
    for claim in envelope.claims:
        assert claim.statement == claim.evidence_span
        assert claim.evidence_span in by_url[claim.source_url]
        assert len(claim.evidence_span) >= 40
        assert len(claim.evidence_span.split()) >= 6


def test_extraction_ignores_a_source_it_did_not_record() -> None:
    model = FixtureResearchModel(_corpus())
    envelope, _ = model.extract(
        company_number=NUMBER,
        company_name=NAME,
        cutoff=CUTOFF,
        sources=[{"url": "https://www.example.org/other", "title": "Other", "text": "Anything."}],
        max_output_tokens=5_000,
    )
    assert envelope.claims == []
