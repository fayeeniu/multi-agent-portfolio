import { NextRequest, NextResponse } from "next/server";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);
const READ_ONLY_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function splitHost(value: string): { hostname: string; port: string } | null {
  const match = value.trim().toLowerCase().match(/^(\[[^\]]+\]|[^:]+)(?::(\d+))?$/);
  if (!match?.[1]) return null;
  return { hostname: match[1], port: match[2] ?? "" };
}

function forbidden(detail: string): NextResponse {
  return NextResponse.json(
    { detail: { code: "local_origin_required", message: detail } },
    { status: 403, headers: { "cache-control": "no-store" } },
  );
}

/** Keep the credential-bearing server proxy bound to the exact local browser origin. */
export function proxy(request: NextRequest): NextResponse {
  const hostHeader = request.headers.get("host") ?? "";
  const host = splitHost(hostHeader);
  if (!host || !LOOPBACK_HOSTS.has(host.hostname)) {
    return forbidden("The control room accepts loopback Host headers only.");
  }

  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite === "cross-site") {
    return forbidden("Cross-site requests are not allowed.");
  }

  const originHeader = request.headers.get("origin");
  if (originHeader) {
    let origin: URL;
    try {
      origin = new URL(originHeader);
    } catch {
      return forbidden("The request Origin is invalid.");
    }
    const originHost = splitHost(origin.host);
    if (
      origin.protocol !== request.nextUrl.protocol ||
      !originHost ||
      originHost.hostname !== host.hostname ||
      originHost.port !== host.port
    ) {
      return forbidden("The request Origin must match the local control room.");
    }
  } else if (!READ_ONLY_METHODS.has(request.method)) {
    return forbidden("State-changing requests require a same-origin Origin header.");
  }

  return NextResponse.next();
}
