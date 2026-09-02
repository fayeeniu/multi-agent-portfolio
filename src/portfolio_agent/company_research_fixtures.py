"""Offline stand-ins for the external research model and the public fetcher.

These exist so the bounded research workflow can be demonstrated and regression
tested without a model call or any outbound request. They are deliberately dumb:
they replay a recorded source map and propose recorded sentences. Every claim
they propose still passes through the same exact-span, cutoff, privacy,
injection and contradiction rules in :mod:`portfolio_agent.company_research`
that live model output passes through, so a fixture run exercises the real
controls rather than bypassing them.

Nothing here is evidence about a real company. Runs driven by these adapters are
synthetic by construction and must be labelled as such wherever they are shown.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .company_research import (
    CompanyResearchError,
    DiscoveredSource,
    ExtractedResearchClaim,
    FetchedPage,
    ModelCallResult,
    ResearchExtractionEnvelope,
    canonical_public_url,
)
from .enums import ResearchClaimCategory

FIXTURE_MODEL_NAME = "offline-fixture-research"
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class FixtureParagraph:
    category: str
    subject_key: str
    perspective: str
    text: str
    event_date: str | None = None
    amount: str | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class FixturePage:
    url: str
    title: str
    media_type: str
    outcome: str
    paragraphs: tuple[FixtureParagraph, ...]


def _slug(company_number: str) -> str:
    # Keyed on the exact identifier rather than the canonical name: until a
    # reviewer confirms identity the name is a generated placeholder.
    cleaned = _SLUG_STRIP.sub("-", company_number.casefold()).strip("-")
    return f"company-{cleaned or 'unknown'}"[:56]


def load_fixture_pages(path: Path) -> tuple[FixturePage, ...]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    pages: list[FixturePage] = []
    for raw in payload.get("pages", []):
        pages.append(
            FixturePage(
                url=str(raw["url"]),
                title=str(raw["title"]),
                media_type=str(raw["media_type"]),
                outcome=str(raw.get("outcome", "ok")),
                paragraphs=tuple(
                    FixtureParagraph(
                        category=str(item["category"]),
                        subject_key=str(item["subject_key"]),
                        perspective=str(item["perspective"]),
                        text=str(item["text"]),
                        event_date=item.get("event_date"),
                        amount=item.get("amount"),
                        currency=item.get("currency"),
                    )
                    for item in raw.get("paragraphs", [])
                ),
            )
        )
    return tuple(pages)


def _fill(value: str, *, company_name: str, company_number: str) -> str:
    return (
        value.replace("{name}", company_name)
        .replace("{number}", company_number)
        .replace("{slug}", _slug(company_number))
    )


def _render_html(page: FixturePage, *, company_name: str, company_number: str) -> bytes:
    title = _fill(page.title, company_name=company_name, company_number=company_number)
    body = "".join(
        f"<p>{_fill(item.text, company_name=company_name, company_number=company_number)}</p>"
        for item in page.paragraphs
    )
    document = (
        "<!doctype html><html><head><title>"
        f"{title}</title><style>.x{{color:red}}</style></head>"
        f"<body><h1>{title}</h1>{body}"
        "<p>Synthetic offline fixture page. It is not a record of any real organisation.</p>"
        "</body></html>"
    )
    return document.encode("utf-8")


class FixtureResearchCorpus:
    """Shared fixture state so the model and the fetcher agree on one URL map.

    Discovery fills the recorded URL templates for one company and registers the
    concrete URLs. Capture then resolves those URLs back to the recorded page.
    A pattern fallback keeps a run replayable after a process restart.
    """

    def __init__(self, pages: tuple[FixturePage, ...]) -> None:
        self._pages = pages
        self._resolved: dict[str, tuple[FixturePage, str, str]] = {}

    @property
    def pages(self) -> tuple[FixturePage, ...]:
        return self._pages

    def resolve(
        self, *, company_name: str, company_number: str, limit: int
    ) -> tuple[tuple[str, FixturePage], ...]:
        filled: list[tuple[str, FixturePage]] = []
        for page in self._pages[: max(1, limit)]:
            url = canonical_public_url(
                _fill(page.url, company_name=company_name, company_number=company_number)
            )
            self._resolved[url] = (page, company_name, company_number)
            filled.append((url, page))
        return tuple(filled)

    def lookup(self, url: str) -> tuple[FixturePage, str, str] | None:
        canonical = canonical_public_url(url)
        recorded = self._resolved.get(canonical)
        if recorded is not None:
            return recorded
        for page in self._pages:
            pattern = re.escape(page.url)
            for token in ("\\{name\\}", "\\{number\\}", "\\{slug\\}"):
                pattern = pattern.replace(token, ".+")
            if re.fullmatch(pattern, canonical):
                return page, "", ""
        return None


class FixtureResearchModel:
    """Replays a recorded source map and recorded candidate sentences."""

    def __init__(self, corpus: FixtureResearchCorpus) -> None:
        self._corpus = corpus
        self.discovery_calls = 0
        self.extraction_calls = 0

    def discover(
        self,
        *,
        company_number: str,
        company_name: str,
        cutoff: date,
        max_sources: int,
        max_tool_calls: int,
        max_output_tokens: int,
        timeout_seconds: float | None = None,
        attempt: int = 1,
    ) -> ModelCallResult:
        del cutoff, max_tool_calls, max_output_tokens, timeout_seconds, attempt
        self.discovery_calls += 1
        sources = tuple(
            DiscoveredSource(
                url,
                _fill(page.title, company_name=company_name, company_number=company_number),
            )
            for url, page in self._corpus.resolve(
                company_name=company_name,
                company_number=company_number,
                limit=max_sources,
            )
        )
        return ModelCallResult(
            output_text="Offline fixture source map",
            model=FIXTURE_MODEL_NAME,
            input_tokens=0,
            output_tokens=0,
            tool_calls=0,
            sources=sources,
        )

    def extract(
        self,
        *,
        company_number: str,
        company_name: str,
        cutoff: date,
        sources: list[dict[str, str]],
        max_output_tokens: int,
        timeout_seconds: float | None = None,
        attempt: int = 1,
    ) -> tuple[ResearchExtractionEnvelope, ModelCallResult]:
        del cutoff, max_output_tokens, timeout_seconds, attempt
        self.extraction_calls += 1
        claims: list[ExtractedResearchClaim] = []
        for source in sources:
            recorded = self._corpus.lookup(source["url"])
            if recorded is None:
                continue
            page = recorded[0]
            for paragraph in page.paragraphs:
                sentence = " ".join(
                    _fill(
                        paragraph.text,
                        company_name=company_name,
                        company_number=company_number,
                    ).split()
                )
                # The validator rejects short or paraphrased spans; propose only
                # a verbatim sentence and let it decide.
                if sentence not in source["text"]:
                    continue
                claims.append(
                    ExtractedResearchClaim(
                        category=ResearchClaimCategory(paragraph.category),
                        subject_key=paragraph.subject_key,
                        statement=sentence,
                        source_url=source["url"],
                        evidence_span=sentence,
                        event_date=paragraph.event_date,
                        amount=paragraph.amount,
                        currency=paragraph.currency,
                        perspective=paragraph.perspective,
                    )
                )
        telemetry = ModelCallResult(
            output_text="Offline fixture extraction",
            model=FIXTURE_MODEL_NAME,
            input_tokens=0,
            output_tokens=0,
            tool_calls=0,
        )
        return ResearchExtractionEnvelope(claims=claims), telemetry


class FixturePublicFetcher:
    """Returns recorded bytes instead of performing an outbound request."""

    def __init__(self, corpus: FixtureResearchCorpus) -> None:
        self._corpus = corpus

    def fetch(
        self,
        url: str,
        *,
        max_response_bytes: int | None = None,
        max_redirects: int | None = None,
        timeout_seconds: float | None = None,
    ) -> FetchedPage:
        del max_redirects, timeout_seconds
        canonical = canonical_public_url(url)
        recorded = self._corpus.lookup(canonical)
        if recorded is None:
            raise CompanyResearchError("No fixture page is recorded for this URL.", code="http_404")
        page, company_name, company_number = recorded
        if page.outcome == "robots_blocked":
            raise CompanyResearchError(
                "Publisher robots policy disallows capture.", code="robots_blocked"
            )
        if page.outcome == "unsupported_media":
            raise CompanyResearchError(
                f"Unsupported media type {page.media_type}.", code="unsupported_media"
            )
        if page.outcome == "fetch_failed":
            raise CompanyResearchError("Recorded transport failure.", code="fetch_failed")
        content = _render_html(
            page,
            company_name=company_name,
            company_number=company_number,
        )
        if max_response_bytes is not None and len(content) > max_response_bytes:
            raise CompanyResearchError("Fixture page exceeds the byte budget.", code="too_large")
        return FetchedPage(
            requested_url=canonical,
            final_url=canonical,
            status_code=200,
            media_type="text/html",
            content=content,
            retrieved_at=datetime.now(UTC),
        )
