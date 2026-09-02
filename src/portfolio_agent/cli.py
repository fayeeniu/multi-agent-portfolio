from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .bootstrap import create_fixture_research_runtime, create_runtime


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portfolio-agent",
        description="Local company-research API for the control-room dashboard.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialise the local database.")

    serve_parser = subparsers.add_parser("serve", help="Run the private research API.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument(
        "--fixture-research",
        action="store_true",
        help=(
            "Serve with an offline fixture research corpus. The full agent workflow runs, "
            "but no external model call and no outbound request is made and every run is "
            "synthetic."
        ),
    )
    serve_parser.add_argument(
        "--docker-local",
        action="store_true",
        help=(
            "Bind inside a container and accept only private container-network clients. "
            "The published host port must still be restricted to loopback."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "serve":
        if not args.docker_local and args.host not in {"127.0.0.1", "localhost", "::1"}:
            raise SystemExit("This service may only bind to a loopback interface.")
        import uvicorn

        from .web import create_app

        serve_runtime = create_fixture_research_runtime() if args.fixture_research else None
        if serve_runtime is not None:
            print(
                "Fixture research enabled: no external model call and no outbound request. "
                "Every run produced in this mode is synthetic.",
                file=sys.stderr,
            )
        uvicorn.run(
            create_app(
                serve_runtime,
                allow_container_network_clients=args.docker_local,
            ),
            host="0.0.0.0" if args.docker_local else args.host,
            port=args.port,
            reload=False,
        )
        return 0

    runtime = create_runtime()
    if args.command == "init-db":
        _json({"database_url": runtime.settings.database_url, "status": "initialised"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
