export function humanize(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const text = value.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function shortHash(value: string | null | undefined, width = 10): string {
  if (!value) return "—";
  return value.length <= width ? value : `${value.slice(0, width)}…`;
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MiB`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString();
}

const STATUS_TONE: Record<string, "evidence" | "human" | "danger" | "idle" | "active"> = {
  succeeded: "evidence",
  approved: "evidence",
  fetched: "evidence",
  verified: "evidence",
  resolved: "evidence",
  running: "active",
  pending: "idle",
  discovered: "idle",
  awaiting: "human",
  pending_review: "human",
  identity_hold: "danger",
  failed: "danger",
  rejected: "danger",
  blocked: "danger",
  cancelled: "idle",
  unsupported: "idle",
};

export function statusTone(status: string): "evidence" | "human" | "danger" | "idle" | "active" {
  return STATUS_TONE[status] ?? "idle";
}

/** Chart colour: queued work reads as in-progress, not complete. */
export function chartTone(status: string): "evidence" | "human" | "danger" | "idle" | "active" {
  if (status === "pending" || status === "discovered") return "active";
  return statusTone(status);
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  running: "Executing",
  succeeded: "Complete",
  failed: "Failed",
  cancelled: "Cancelled",
  awaiting: "Awaiting review",
  pending_review: "Awaiting review",
  approved: "Approved",
  rejected: "Rejected",
  discovered: "Candidate",
  fetched: "Captured",
  blocked: "Blocked by policy",
  unsupported: "Unsupported media",
  identity_hold: "Identity held",
  ready: "Ready",
};

export function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? humanize(status);
}

/** Short display form for an OpenAI model id, e.g. `gpt-5.4-mini` -> `5.4-mini`. */
export function shortModel(value: string | null | undefined): string {
  if (!value) return "—";
  if (value === "offline-fixture-research") return "fixture";
  return value.replace(/^gpt-/, "");
}
