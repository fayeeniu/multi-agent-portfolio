from __future__ import annotations

import ipaddress
import secrets
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .api import create_api_router
from .bootstrap import Runtime, create_runtime
from .company_research import CompanyResearchError

CSRF_COOKIE = "portfolio_csrf"
ALLOWED_HOST_HEADERS = {"127.0.0.1", "localhost", "::1", "testserver", "api"}
ALLOWED_CLIENTS = {"127.0.0.1", "::1", "testclient"}
CONTAINER_CLIENT_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def _host_without_port(value: str) -> str:
    lowered = value.strip().casefold()
    if lowered.startswith("[") and "]" in lowered:
        return lowered[1 : lowered.index("]")]
    return lowered.split(":", 1)[0]


def _client_is_allowed(value: str, *, allow_container_network_clients: bool) -> bool:
    if value in ALLOWED_CLIENTS:
        return True
    if not allow_container_network_clients:
        return False
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(address in network for network in CONTAINER_CLIENT_NETWORKS)


def create_app(
    runtime: Runtime | None = None, *, allow_container_network_clients: bool = False
) -> FastAPI:
    """Create the private API used by the Next.js server-side proxy."""

    selected = runtime or create_runtime()
    app = FastAPI(
        title="Portfolio evidence API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.runtime = selected
    app.state.csrf_token = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        client_host = request.client.host if request.client is not None else ""
        host_header = _host_without_port(request.headers.get("host", ""))
        if (
            not _client_is_allowed(
                client_host,
                allow_container_network_clients=allow_container_network_clients,
            )
            or host_header not in ALLOWED_HOST_HEADERS
        ):
            return PlainTextResponse("Local loopback access only.", status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        if request.cookies.get(CSRF_COOKIE) != app.state.csrf_token:
            response.set_cookie(
                CSRF_COOKIE,
                app.state.csrf_token,
                httponly=True,
                samesite="strict",
                secure=False,
                path="/",
            )
        return response

    @app.exception_handler(CompanyResearchError)
    async def company_research_error(_request: Request, exc: CompanyResearchError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": getattr(exc, "code", "company_research_error"),
                    "message": str(exc),
                }
            },
        )

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "external_llm": (
                "enabled" if selected.company_research is not None else "disabled-by-default"
            ),
        }

    app.include_router(
        create_api_router(
            selected,
            csrf_token=app.state.csrf_token,
            csrf_cookie=CSRF_COOKIE,
        )
    )

    return app
