"""Contract tests for the JSON projection layer the control room renders from.

These assert that the API reports persisted state truthfully: closed gates read
as closed, an unreviewed identifier blocks research, the run graph mirrors the
persisted tasks and source rows, and approval still requires a named reviewer
with a matching lock version.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from portfolio_agent import company_research
from portfolio_agent.bootstrap import Runtime, create_fixture_research_runtime, project_root
from portfolio_agent.config import Settings
from portfolio_agent.web import create_app

PURPOSE = "Assemble cited public evidence about this company for an investment review."
NUMBER = "09339981"


@pytest.fixture
def fixture_runtime(tmp_path: Path) -> Iterator[Runtime]:
    settings = Settings(
        project_root=project_root(),
        database_url=f"sqlite:///{tmp_path / 'control-room.db'}",
        raw_data_dir=tmp_path / "raw",
        source_snapshot_dir=tmp_path / "sources",
        reviewer_name="Synthetic Test Reviewer",
    )
    created = create_fixture_research_runtime(settings)
    try:
        yield created
    finally:
        created.engine.dispose()


def _client(runtime: Runtime) -> tuple[TestClient, str]:
    app = create_app(runtime)
    client = TestClient(app)
    token = client.get("/api/session").json()["csrf_token"]
    return client, token


def _open_case(client: TestClient, token: str) -> tuple[str, str]:
    created = client.post(
        "/api/company-intakes",
        json={
            "csrf_token": token,
            "purpose": PURPOSE,
            "classification": "public",
            "companies_house_number": NUMBER,
        },
    )
    assert created.status_code == 201, created.text
    company_id = created.json()["company_id"]
    identifier = created.json()["company"]["identifiers"][0]
    accepted = client.post(
        f"/api/company-identifiers/{identifier['id']}/decide",
        json={
            "csrf_token": token,
            "decision": "accept",
            "reason": "Confirmed the exact number against the register extract.",
        },
    )
    assert accepted.status_code == 200, accepted.text
    return company_id, accepted.json()["cases"][0]["id"]


@pytest.mark.integration
def test_closed_gates_are_reported_as_closed(runtime: Runtime) -> None:
    client, _ = _client(runtime)
    session = client.get("/api/session").json()
    assert session["system"]["research_mode"] == "closed"
    assert session["system"]["live_research_enabled"] is False
    assert "closed by default" in session["system"]["boundary"]
    assert session["system"]["model_route"]["selection"] == {
        "model": "gpt-5.6-luna",
        "effort": "high",
        "stages": ["extract_claims"],
    }
    assert session["system"]["model_route"]["repair"]["effort"] == "high"
    assert [role["key"] for role in session["system"]["agents"]] == [
        "identity",
        "discover_sources",
        "capture_sources",
        "extract_claims",
        "compose_deck",
        "human_review",
    ]


@pytest.mark.integration
def test_research_start_is_refused_while_gates_are_closed(runtime: Runtime) -> None:
    client, token = _client(runtime)
    _, case_id = _open_case(client, token)
    refused = client.post(f"/api/research-cases/{case_id}/runs", json={"csrf_token": token})
    assert refused.status_code == 409
    assert "closed" in refused.json()["detail"]


@pytest.mark.integration
def test_mutations_require_a_matching_csrf_token(runtime: Runtime) -> None:
    client, _ = _client(runtime)
    refused = client.post(
        "/api/company-intakes",
        json={"csrf_token": "not-the-process-token", "companies_house_number": NUMBER},
    )
    assert refused.status_code == 403


@pytest.mark.integration
def test_identity_hold_blocks_research_until_a_named_decision(runtime: Runtime) -> None:
    client, token = _client(runtime)
    created = client.post(
        "/api/company-intakes",
        json={
            "csrf_token": token,
            "purpose": PURPOSE,
            "classification": "public",
            "companies_house_number": NUMBER,
        },
    )
    assert created.status_code == 201
    held = created.json()["company"]
    assert held["next_action"]["label"] == "Review exact identifier"
    assert held["identifiers"][0]["state"] == "pending"

    overview = client.get("/api/overview").json()
    assert overview["metrics"]["identity_holds"] == 1
    assert any(item["kind"] == "Identity" for item in overview["attention"])

    identifier_id = held["identifiers"][0]["id"]
    resolved = client.post(
        f"/api/company-identifiers/{identifier_id}/decide",
        json={
            "csrf_token": token,
            "decision": "accept",
            "reason": "Confirmed the exact number against the register extract.",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["identifiers"][0]["state"] == "accepted"
    assert resolved.json()["company"]["name"] == f"Company {NUMBER}"
    assert client.get("/api/overview").json()["metrics"]["identity_holds"] == 0


@pytest.mark.integration
def test_run_advance_marks_a_transient_stage_failure_as_automatically_retryable(
    fixture_runtime: Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)
    run_id = client.post(
        f"/api/research-cases/{case_id}/runs", json={"csrf_token": token}
    ).json()["run"]["id"]
    assert fixture_runtime.company_research is not None
    model = fixture_runtime.company_research._model
    original = model.discover
    calls = 0

    def flaky_discovery(**kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Synthetic transient planning failure")
        return original(**kwargs)

    monkeypatch.setattr(model, "discover", flaky_discovery)

    failed = client.post(
        f"/api/research-runs/{run_id}/advance", json={"csrf_token": token}
    )
    assert failed.status_code == 200
    assert failed.json()["advance"] == {
        "ok": False,
        "capability": "discover_sources",
        "code": "task_failed",
        "message": "Research stage failed without persisting provider or source content.",
        "elapsed_ms": failed.json()["advance"]["elapsed_ms"],
        "retryable": True,
        "attempts_remaining": 1,
    }

    retried = client.post(
        f"/api/research-runs/{run_id}/advance", json={"csrf_token": token}
    )
    assert retried.status_code == 200
    assert retried.json()["advance"]["ok"] is True
    assert retried.json()["advance"]["capability"] == "discover_sources"
    assert calls == 2


@pytest.mark.integration
def test_model_timeout_is_recorded_as_a_safe_automatically_retryable_failure(
    fixture_runtime: Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)
    run_id = client.post(
        f"/api/research-cases/{case_id}/runs", json={"csrf_token": token}
    ).json()["run"]["id"]
    assert fixture_runtime.company_research is not None
    model = fixture_runtime.company_research._model

    def timed_out_discovery(**kwargs: Any) -> Any:
        del kwargs
        raise company_research.CompanyResearchError(
            "The model request timed out before returning a usable response.",
            code="model_timeout",
        )

    monkeypatch.setattr(model, "discover", timed_out_discovery)

    failed = client.post(
        f"/api/research-runs/{run_id}/advance", json={"csrf_token": token}
    )
    assert failed.status_code == 200
    assert failed.json()["advance"] == {
        "ok": False,
        "capability": "discover_sources",
        "code": "model_timeout",
        "message": "The model request timed out before returning a usable response.",
        "elapsed_ms": failed.json()["advance"]["elapsed_ms"],
        "retryable": True,
        "attempts_remaining": 1,
    }


@pytest.mark.integration
def test_terminal_run_can_restart_from_stage_one_without_mutating_history(
    fixture_runtime: Runtime,
) -> None:
    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)
    original_id = client.post(
        f"/api/research-cases/{case_id}/runs", json={"csrf_token": token}
    ).json()["run"]["id"]
    for _ in range(4):
        advanced = client.post(
            f"/api/research-runs/{original_id}/advance", json={"csrf_token": token}
        )
        assert advanced.status_code == 200
        assert advanced.json()["advance"]["ok"] is True
    profile = client.get(f"/api/research-runs/{original_id}").json()["profile"]
    approved = client.post(
        f"/api/profile-versions/{profile['id']}/decide",
        json={
            "csrf_token": token,
            "decision": "approve",
            "reason": "Reviewed the cited spans before starting a fresh test run.",
            "expected_lock_version": profile["lock_version"],
        },
    )
    assert approved.status_code == 200
    assert approved.json()["run"]["status"] == "approved"

    restarted = client.post(
        f"/api/research-runs/{original_id}/restart", json={"csrf_token": token}
    )
    assert restarted.status_code == 201
    fresh = restarted.json()
    assert fresh["run"]["id"] != original_id
    assert fresh["run"]["research_case_id"] == case_id
    assert fresh["run"]["status"] == "pending"
    assert fresh["run"]["coverage"]["restarted_from_run_id"] == original_id
    assert [node["status"] for node in fresh["nodes"][1:]] == ["pending"] * 5
    assert client.get(f"/api/research-runs/{original_id}").json()["run"]["status"] == "approved"

    duplicate = client.post(
        f"/api/research-runs/{original_id}/restart", json={"csrf_token": token}
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["run"]["id"] == fresh["run"]["id"]

    fresh_id = fresh["run"]["id"]
    for _ in range(4):
        advanced = client.post(
            f"/api/research-runs/{fresh_id}/advance", json={"csrf_token": token}
        )
        assert advanced.status_code == 200
        assert advanced.json()["advance"]["ok"] is True
    fresh_profile = client.get(f"/api/research-runs/{fresh_id}").json()["profile"]
    fresh_approved = client.post(
        f"/api/profile-versions/{fresh_profile['id']}/decide",
        json={
            "csrf_token": token,
            "decision": "approve",
            "reason": "Reviewed the complete fresh-run evidence and restart lineage.",
            "expected_lock_version": fresh_profile["lock_version"],
        },
    )
    assert fresh_approved.status_code == 200
    assert fresh_approved.json()["run"]["status"] == "approved"
    assert (
        fresh_approved.json()["run"]["coverage"]["restarted_from_run_id"]
        == original_id
    )


@pytest.mark.integration
def test_active_run_cannot_restart_from_stage_one(fixture_runtime: Runtime) -> None:
    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)
    run_id = client.post(
        f"/api/research-cases/{case_id}/runs", json={"csrf_token": token}
    ).json()["run"]["id"]

    blocked = client.post(
        f"/api/research-runs/{run_id}/restart", json={"csrf_token": token}
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["code"] == "run_not_restartable"


@pytest.mark.integration
def test_intake_rejects_an_unusable_company_number(runtime: Runtime) -> None:
    client, token = _client(runtime)
    refused = client.post(
        "/api/company-intakes",
        json={"csrf_token": token, "purpose": PURPOSE, "companies_house_number": "!!"},
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["message"]


@pytest.mark.integration
def test_unknown_run_is_not_invented(fixture_runtime: Runtime) -> None:
    client, _ = _client(fixture_runtime)
    assert client.get("/api/research-runs/crun_missing").status_code == 404


@pytest.mark.integration
def test_fixture_run_projects_the_persisted_graph_and_evidence(
    fixture_runtime: Runtime,
) -> None:
    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)

    started = client.post(f"/api/research-cases/{case_id}/runs", json={"csrf_token": token})
    assert started.status_code == 201, started.text
    run_id = started.json()["run"]["id"]

    pending = started.json()
    assert [node["id"] for node in pending["nodes"]] == [
        "identity",
        "discover_sources",
        "capture_sources",
        "extract_claims",
        "compose_deck",
        "human_review",
    ]
    assert [node["status"] for node in pending["nodes"][1:]] == ["pending"] * 5
    assert pending["edges"][0] == {
        "from": "identity",
        "to": "discover_sources",
        "kind": "spine",
    }

    capabilities: list[str] = []
    for _ in range(4):
        response = client.post(f"/api/research-runs/{run_id}/advance", json={"csrf_token": token})
        assert response.status_code == 200, response.text
        advance = response.json()["advance"]
        assert advance["ok"] is True, advance
        capabilities.append(advance["capability"])
    assert capabilities == [
        "discover_sources",
        "capture_sources",
        "extract_claims",
        "compose_deck",
    ]

    state = client.get(f"/api/research-runs/{run_id}").json()
    assert state["run"]["status"] == "pending_review"
    assert state["run"]["company_name"] == f"Company {NUMBER}"
    assert [node["status"] for node in state["nodes"]] == [
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
        "awaiting",
    ]
    assert state["nodes"][1]["route"]["model"] == "offline-fixture-research"
    assert state["nodes"][3]["route"]["model"] == "offline-fixture-research"

    lane_states = {lane["status"] for lane in state["lanes"]}
    assert {"fetched", "blocked", "unsupported", "failed"} <= lane_states
    blocked = next(lane for lane in state["lanes"] if lane["status"] == "blocked")
    assert blocked["error_code"] == "robots_blocked"
    assert blocked["raw_sha256"] is None
    captured = next(lane for lane in state["lanes"] if lane["status"] == "fetched")
    assert len(captured["raw_sha256"]) == 64

    assert state["claims"]
    lane_ids = {lane["id"] for lane in state["lanes"]}
    for claim in state["claims"]:
        # Every admitted claim is a verbatim span of a captured snapshot and
        # resolves to the lane it came from.
        assert claim["statement"] == claim["evidence_span"]
        assert claim["source_id"] in lane_ids
        assert claim["extraction_method"] == "openai_verbatim_exact_span"

    assert state["contradictions"], "the fixture corpus disagrees on one funding subject"
    contradiction = state["contradictions"][0]
    assert contradiction["status"] == "requires_named_resolution"
    assert len({item["source_url"] for item in contradiction["claims"]}) > 1

    profile = state["profile"]
    assert profile is not None
    assert profile["status"] == "pending_review"
    investment_report = profile["content"]["investment_report"]
    assert investment_report["summary"]["defined_metrics"] == 37
    assert investment_report["summary"]["publicly_evidenced"] == 2
    assert investment_report["summary"]["definition_required"] == 8
    assert len(investment_report["report_sections"]) == 10
    report_row = next(
        row for row in client.get("/api/overview").json()["runs"] if row["id"] == run_id
    )
    assert report_row["profile"]["id"] == profile["id"]
    assert report_row["profile"]["status"] == "pending_review"
    assert state["next_action"]["label"].startswith("Approve or reject version")


@pytest.mark.integration
def test_profile_approval_requires_the_expected_lock_version(
    fixture_runtime: Runtime,
) -> None:
    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)
    run_id = client.post(
        f"/api/research-cases/{case_id}/runs", json={"csrf_token": token}
    ).json()["run"]["id"]
    for _ in range(4):
        client.post(f"/api/research-runs/{run_id}/advance", json={"csrf_token": token})
    profile: dict[str, Any] = client.get(f"/api/research-runs/{run_id}").json()["profile"]

    stale = client.post(
        f"/api/profile-versions/{profile['id']}/decide",
        json={
            "csrf_token": token,
            "decision": "approve",
            "reason": "Reviewed the cited spans and the contradiction ledger.",
            "expected_lock_version": profile["lock_version"] + 5,
        },
    )
    assert stale.status_code == 422

    approved = client.post(
        f"/api/profile-versions/{profile['id']}/decide",
        json={
            "csrf_token": token,
            "decision": "approve",
            "reason": "Reviewed the cited spans and the contradiction ledger.",
            "expected_lock_version": profile["lock_version"],
        },
    )
    assert approved.status_code == 200
    assert approved.json()["run"]["status"] == "approved"
    assert approved.json()["profile"]["reviewed_by"] == "Synthetic Test Reviewer"
    assert approved.json()["nodes"][-1]["status"] == "succeeded"


@pytest.mark.integration
def test_a_superseded_run_stays_readable_but_cannot_be_advanced(
    fixture_runtime: Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prompt version change must not strand completed work.

    Tamper detection is the fingerprint reproducing from the run's own persisted
    fields, so a finished run stays readable and its approved deck stays
    downloadable. Executing a stage under changed rules is what must fail.
    """

    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)
    run_id = client.post(
        f"/api/research-cases/{case_id}/runs", json={"csrf_token": token}
    ).json()["run"]["id"]
    for _ in range(2):
        client.post(f"/api/research-runs/{run_id}/advance", json={"csrf_token": token})

    superseded = "company-research-web-v11"
    monkeypatch.setattr(company_research, "PROMPT_VERSION", superseded)
    monkeypatch.setattr(
        company_research,
        "ADMITTED_PROMPT_VERSIONS",
        frozenset({*company_research.ADMITTED_PROMPT_VERSIONS, superseded}),
    )

    # Reading the run is unaffected: the projection reads persisted rows.
    state = client.get(f"/api/research-runs/{run_id}").json()
    assert state["run"]["prompt_version"] == "company-research-web-v10"
    assert [node["status"] for node in state["nodes"][:3]] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]

    blocked = client.post(f"/api/research-runs/{run_id}/advance", json={"csrf_token": token})
    assert blocked.status_code == 200
    assert blocked.json()["advance"]["ok"] is False
    assert blocked.json()["advance"]["code"] == "run_contract_stale"

    # The run can still be closed out by a named reviewer.
    cancelled = client.post(
        f"/api/research-runs/{run_id}/cancel",
        json={"csrf_token": token, "reason": "Superseded by a new prompt version."},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["run"]["status"] == "cancelled"


@pytest.mark.integration
def test_an_approved_deck_survives_a_prompt_version_change(
    fixture_runtime: Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token = _client(fixture_runtime)
    _, case_id = _open_case(client, token)
    run_id = client.post(
        f"/api/research-cases/{case_id}/runs", json={"csrf_token": token}
    ).json()["run"]["id"]
    for _ in range(4):
        client.post(f"/api/research-runs/{run_id}/advance", json={"csrf_token": token})
    profile: dict[str, Any] = client.get(f"/api/research-runs/{run_id}").json()["profile"]
    approved = client.post(
        f"/api/profile-versions/{profile['id']}/decide",
        json={
            "csrf_token": token,
            "decision": "approve",
            "reason": "Reviewed the cited spans before the prompt change.",
            "expected_lock_version": profile["lock_version"],
        },
    )
    assert approved.status_code == 200

    superseded = "company-research-web-v4"
    monkeypatch.setattr(company_research, "PROMPT_VERSION", superseded)
    monkeypatch.setattr(
        company_research,
        "ADMITTED_PROMPT_VERSIONS",
        frozenset({*company_research.ADMITTED_PROMPT_VERSIONS, superseded}),
    )

    replay = client.get(f"/api/research-runs/{run_id}")
    assert replay.status_code == 200, replay.text
    locked = replay.json()["profile"]
    assert locked["id"] == profile["id"]
    assert locked["status"] == "approved"
    assert locked["content_sha256"] == profile["content_sha256"]
