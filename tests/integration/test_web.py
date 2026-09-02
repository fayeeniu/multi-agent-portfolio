from __future__ import annotations

from fastapi.testclient import TestClient

from portfolio_agent.bootstrap import Runtime
from portfolio_agent.web import create_app


def test_private_api_health_security_headers_and_removed_legacy_routes(runtime: Runtime) -> None:
    client = TestClient(create_app(runtime))

    health = client.get("/healthz")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "external_llm": "disabled-by-default"}
    assert health.headers["cache-control"] == "no-store"
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["content-security-policy"] == (
        "default-src 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    assert client.get("/").status_code == 404
    assert client.get("/companies").status_code == 404
    assert client.get("/runs/run_missing").status_code == 404
    assert client.get("/reports/report_missing").status_code == 404
    assert client.get("/static/styles.css").status_code == 404


def test_container_local_mode_accepts_only_private_clients_and_exact_api_host(
    runtime: Runtime,
) -> None:
    private_client = ("172.18.0.1", 50000)
    public_client = ("8.8.8.8", 50000)

    default_response = TestClient(create_app(runtime), client=private_client).get(
        "/healthz", headers={"host": "api:8000"}
    )
    container_response = TestClient(
        create_app(runtime, allow_container_network_clients=True), client=private_client
    ).get("/healthz", headers={"host": "api:8000"})
    public_response = TestClient(
        create_app(runtime, allow_container_network_clients=True), client=public_client
    ).get("/healthz", headers={"host": "api:8000"})
    forged_host_response = TestClient(
        create_app(runtime, allow_container_network_clients=True), client=private_client
    ).get("/healthz", headers={"host": "attacker.example"})

    assert default_response.status_code == 403
    assert container_response.status_code == 200
    assert public_response.status_code == 403
    assert forged_host_response.status_code == 403
