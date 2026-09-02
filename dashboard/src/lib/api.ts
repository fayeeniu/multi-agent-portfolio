export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function describe(payload: unknown, status: number): ApiError {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return new ApiError(detail, status, null);
    if (detail && typeof detail === "object") {
      const record = detail as { message?: string; code?: string };
      return new ApiError(record.message ?? "Request failed.", status, record.code ?? null);
    }
  }
  return new ApiError(`Request failed with status ${status}.`, status, null);
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/dash-api/${path}`, { signal, cache: "no-store" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw describe(payload, response.status);
  return payload as T;
}

export async function apiPost<T>(
  path: string,
  body: Record<string, unknown> = {},
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`/dash-api/${path}`, {
    method: "POST",
    signal,
    cache: "no-store",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw describe(payload, response.status);
  return payload as T;
}

export async function apiUpload<T>(path: string, body: FormData, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/dash-api/${path}`, {
    method: "POST",
    signal,
    cache: "no-store",
    body,
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw describe(payload, response.status);
  return payload as T;
}
