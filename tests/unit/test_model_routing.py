"""Model routing and instruction contract for the company-research stages.

Routing is fixed in code, never chosen by a model. All stages use the approved
Luna model; planning uses configured reasoning effort while bounded selection
and repair use high effort. These tests pin what is actually sent to the API,
because that is the part a reader cannot verify from persisted records alone.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

from portfolio_agent import company_research
from portfolio_agent.company_research import (
    OpenAICompanyResearchClient,
    _discovery_instructions,
    _extraction_instructions,
)
from portfolio_agent.config import (
    APPROVED_OPENAI_ESCALATION_MODEL,
    APPROVED_OPENAI_MODEL,
    Settings,
)

CUTOFF = date(2026, 8, 27)


def _settings(tmp_path: Path, **overrides: Any) -> Settings:
    base = Settings(
        project_root=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'routing.db'}",
        raw_data_dir=tmp_path / "raw",
        allow_external_llm=True,
        allow_live_public_retrieval=True,
        reviewer_name="Synthetic Test Reviewer",
    )
    return replace(base, **overrides) if overrides else base


class _Recorder:
    """Captures the exact keyword arguments sent to the Responses API."""

    def __init__(
        self,
        output_text: str = (
            '{"sources":[{"url":"https://example.com/a",'
            '"title":"Example source","category":"other"}]}'
        ),
        *,
        output_tokens: int = 5,
        status: str = "completed",
        incomplete_reason: str | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._output_text = output_text
        self._output_tokens = output_tokens
        self._status = status
        self._incomplete_reason = incomplete_reason

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        incomplete = (
            SimpleNamespace(reason=self._incomplete_reason)
            if self._incomplete_reason is not None
            else None
        )
        return SimpleNamespace(
            output_text=self._output_text,
            model=kwargs["model"],
            usage=SimpleNamespace(input_tokens=10, output_tokens=self._output_tokens),
            output=[],
            status=self._status,
            incomplete_details=incomplete,
        )


def _client(tmp_path: Path, recorder: _Recorder, **overrides: Any) -> OpenAICompanyResearchClient:
    return OpenAICompanyResearchClient(
        _settings(tmp_path, **overrides), client=SimpleNamespace(responses=recorder)
    )


def test_discovery_uses_configured_effort_and_selection_uses_high_effort(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path, _Recorder())
    assert client.route("discover_sources", 1) == (APPROVED_OPENAI_ESCALATION_MODEL, "medium")
    assert client.route("extract_claims", 1) == (APPROVED_OPENAI_MODEL, "high")


def test_a_repeat_attempt_uses_luna_at_high_effort(tmp_path: Path) -> None:
    client = _client(tmp_path, _Recorder())
    for capability in ("discover_sources", "extract_claims"):
        assert client.route(capability, 2) == (APPROVED_OPENAI_MODEL, "high")


def test_a_stage_outside_the_reasoning_set_uses_luna_at_high_effort(tmp_path: Path) -> None:
    client = _client(tmp_path, _Recorder())
    assert client.route("compose_deck", 1) == (APPROVED_OPENAI_MODEL, "high")


@pytest.mark.parametrize("effort", ("high", "xhigh", "max"))
def test_configured_reasoning_effort_is_honoured(tmp_path: Path, effort: str) -> None:
    client = _client(tmp_path, _Recorder(), openai_reasoning_effort=effort)
    assert client.route("discover_sources", 1) == (APPROVED_OPENAI_ESCALATION_MODEL, effort)
    assert client.route("extract_claims", 1) == (APPROVED_OPENAI_MODEL, "high")


def test_an_unapproved_pair_or_effort_fails_before_the_client_is_built(tmp_path: Path) -> None:
    recorder = _Recorder()
    with pytest.raises(ValueError, match="approved reasoning model"):
        _client(tmp_path, recorder, openai_escalation_model="gpt-4o")
    with pytest.raises(ValueError, match="Reasoning effort"):
        _client(tmp_path, recorder, openai_reasoning_effort="maximum")
    with pytest.raises(ValueError, match="approved model"):
        _client(tmp_path, recorder, openai_model="gpt-4o-mini")


def test_provider_timeout_is_mapped_to_a_safe_domain_error(tmp_path: Path) -> None:
    class TimeoutResponses:
        def create(self, **kwargs: Any) -> Any:
            del kwargs
            raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))

    client = OpenAICompanyResearchClient(
        _settings(tmp_path), client=SimpleNamespace(responses=TimeoutResponses())
    )
    with pytest.raises(company_research.CompanyResearchError) as caught:
        client.discover(
            company_number="00000006",
            company_name="Example Ltd",
            cutoff=CUTOFF,
            max_sources=8,
            max_tool_calls=12,
            max_output_tokens=500,
        )
    assert caught.value.code == "model_timeout"
    assert str(caught.value) == "The model request timed out before returning a usable response."


@pytest.mark.parametrize(
    ("status_code", "expected_code", "expected_message"),
    (
        (401, "model_authentication_failed", "rejected the configured API key"),
        (403, "model_access_denied", "does not permit this model or Web Search"),
        (429, "model_rate_limited", "rate-limited the model request"),
        (500, "model_service_error", "temporary error"),
        (400, "model_request_rejected", "rejected the model request"),
    ),
)
def test_provider_status_error_is_mapped_without_persisting_provider_content(
    tmp_path: Path,
    status_code: int,
    expected_code: str,
    expected_message: str,
) -> None:
    class FailedResponses:
        def create(self, **kwargs: Any) -> Any:
            del kwargs
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            response = httpx.Response(status_code, request=request)
            raise APIStatusError(
                "provider body must not cross the application boundary",
                response=response,
                body={"error": {"message": "provider body must not be persisted"}},
            )

    client = OpenAICompanyResearchClient(
        _settings(tmp_path), client=SimpleNamespace(responses=FailedResponses())
    )
    with pytest.raises(company_research.CompanyResearchError) as caught:
        client.discover(
            company_number="00000006",
            company_name="Example Ltd",
            cutoff=CUTOFF,
            max_sources=8,
            max_tool_calls=12,
            max_output_tokens=500,
        )
    assert caught.value.code == expected_code
    assert expected_message in str(caught.value)
    assert "provider body" not in str(caught.value)


def test_discovery_sends_the_routed_model_and_effort(tmp_path: Path) -> None:
    recorder = _Recorder()
    client = _client(tmp_path, recorder)
    for attempt in (1, 2):
        client.discover(
            company_number="00000006",
            company_name="Example Ltd",
            cutoff=CUTOFF,
            max_sources=8,
            max_tool_calls=12,
            max_output_tokens=500,
            attempt=attempt,
        )
    first, second = recorder.calls
    assert first["model"] == APPROVED_OPENAI_ESCALATION_MODEL
    assert first["reasoning"] == {"effort": "medium"}
    assert first["store"] is False
    assert second["model"] == APPROVED_OPENAI_MODEL
    assert second["reasoning"] == {"effort": "high"}


def test_discovery_sends_max_effort_to_the_responses_api(tmp_path: Path) -> None:
    recorder = _Recorder()
    client = _client(tmp_path, recorder, openai_reasoning_effort="max")

    client.discover(
        company_number="00000006",
        company_name="Example Ltd",
        cutoff=CUTOFF,
        max_sources=8,
        max_tool_calls=12,
        max_output_tokens=500,
    )

    assert recorder.calls[0]["reasoning"] == {"effort": "max"}


def test_extraction_sends_the_routed_model_and_keeps_the_strict_schema(tmp_path: Path) -> None:
    recorder = _Recorder(output_text='{"claims": []}')
    client = _client(tmp_path, recorder)
    for attempt in (1, 2):
        client.extract(
            company_number="00000006",
            company_name="Example Ltd",
            cutoff=CUTOFF,
            sources=[{"url": "https://example.com/a", "title": "A", "text": "text"}],
            max_output_tokens=500,
            attempt=attempt,
        )
    first, second = recorder.calls
    assert first["model"] == APPROVED_OPENAI_MODEL
    assert first["reasoning"] == {"effort": "high"}
    assert second["model"] == APPROVED_OPENAI_MODEL
    assert second["reasoning"] == {"effort": "high"}
    for call in (first, second):
        assert call["store"] is False
        assert call["text"]["format"]["strict"] is True


def test_truncated_extraction_is_mapped_without_leaking_provider_text(
    tmp_path: Path,
) -> None:
    recorder = _Recorder(
        output_text='{"claims":[{"category":"funding"',
        output_tokens=10_000,
        status="incomplete",
        incomplete_reason="max_output_tokens",
    )
    client = _client(tmp_path, recorder)
    with pytest.raises(company_research.CompanyResearchError) as caught:
        client.extract(
            company_number="00000006",
            company_name="Example Ltd",
            cutoff=CUTOFF,
            sources=[{"url": "https://example.com/a", "title": "A", "text": "text"}],
            max_output_tokens=10_000,
        )
    assert caught.value.code == "model_output_truncated"
    assert "output-token cap" in str(caught.value)
    assert caught.value.telemetry is not None
    assert caught.value.telemetry.output_tokens == 10_000
    assert '{"claims"' not in str(caught.value)


def test_extraction_that_hits_the_token_cap_is_truncated_not_schema_invalid(
    tmp_path: Path,
) -> None:
    recorder = _Recorder(output_text="not-json", output_tokens=24_000)
    client = _client(tmp_path, recorder)
    with pytest.raises(company_research.CompanyResearchError) as caught:
        client.extract(
            company_number="00000006",
            company_name="Example Ltd",
            cutoff=CUTOFF,
            sources=[{"url": "https://example.com/a", "title": "A", "text": "text"}],
            max_output_tokens=24_000,
        )
    assert caught.value.code == "model_output_truncated"
    assert caught.value.telemetry is not None
    assert caught.value.telemetry.output_tokens == 24_000


def test_the_extraction_brief_states_every_rule_the_validator_enforces() -> None:
    brief = _extraction_instructions(cutoff=CUTOFF, attempt=1)
    # Anything the application checks but the brief omits becomes wasted output.
    for rule in (
        "character for character",
        "exactly the same string as evidence_span",
        "at least 40 characters",
        "at least 6 words",
        "no email address and no telephone number",
        "[personal contact redacted]",
        "no date later than 2026-08-27",
        "appears literally inside the span",
        'perspective "public_discourse" is valid only with category "public_discourse"',
        "lowercase snake_case",
        "Return every distinct material claim",
        "legal name, registered address, status, incorporation date",
        "customers, partnerships, contracts",
        "private_funding_event",
        "shown as context, not counted as a completed metric",
    ):
        assert rule in brief, rule
    assert "CORRECTIVE RETRY" not in brief


def test_the_discovery_brief_states_the_identity_and_source_boundaries() -> None:
    brief = _discovery_instructions(cutoff=CUTOFF, max_sources=9, attempt=1)
    for rule in (
        "Companies House number is the only authoritative identity",
        "Never return a search-engine results page",
        "LinkedIn",
        "no login, no paywall bypass",
        "2026-08-27",
        "at most 9 distinct",
        "registered office, status, incorporation date and SIC codes",
        "funding, investment, grant, customer, partnership",
        "CBIT PUBLIC-METRIC SEARCH TARGETS",
        "investor portfolio pages, law-firm transaction announcements",
        "named customer case studies and procurement references",
        "Select the final evidence candidates yourself",
    ):
        assert rule in brief, rule


def test_a_retry_brief_adds_a_corrective_instruction() -> None:
    for brief in (
        _discovery_instructions(cutoff=CUTOFF, max_sources=9, attempt=2),
        _extraction_instructions(cutoff=CUTOFF, attempt=2),
    ):
        assert "CORRECTIVE RETRY" in brief
