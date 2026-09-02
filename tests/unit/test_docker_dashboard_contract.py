from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_docker_build_and_compose_make_nextjs_the_only_dashboard() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "AS dashboard-build" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm run build" in dockerfile
    assert "AS dashboard-runtime" in dockerfile
    assert '["node", "server.js"]' in dockerfile

    assert "  api:" in compose
    assert "      target: runtime" in compose
    assert "  app:" in compose
    assert "      target: dashboard-runtime" in compose
    assert "PORTFOLIO_API_ORIGIN: http://api:8000" in compose
    assert '127.0.0.1:${PORTFOLIO_PORT:-8000}:3000' in compose
    assert "condition: service_healthy" in compose

    ignored_lines = {
        line.strip()
        for line in dockerignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "dashboard" not in ignored_lines
    assert "dashboard/node_modules" in ignored_lines
    assert "dashboard/.next" in ignored_lines


def test_legacy_server_rendered_dashboard_assets_are_gone() -> None:
    package = ROOT / "src" / "portfolio_agent"

    assert not (package / "dashboard.py").exists()
    assert not list((package / "templates").glob("*.html"))
    assert not (package / "static" / "control-room.js").exists()
    assert not (package / "static" / "styles.css").exists()
    assert not (package / "static" / "company-deck.css").exists()
    assert not (ROOT / "dashboard" / "src" / "app" / "deck").exists()


def test_nextjs_proxy_guards_the_private_api_credentials_with_local_origin_checks() -> None:
    proxy = (ROOT / "dashboard" / "src" / "proxy.ts").read_text(encoding="utf-8")

    assert 'new Set(["127.0.0.1", "localhost", "[::1]"])' in proxy
    assert 'request.headers.get("host")' in proxy
    assert 'request.headers.get("origin")' in proxy
    assert 'request.headers.get("sec-fetch-site")' in proxy
    assert "originHost.hostname !== host.hostname" in proxy
    assert "originHost.port !== host.port" in proxy
    assert "!READ_ONLY_METHODS.has(request.method)" in proxy
