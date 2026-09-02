"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api";
import { ErrorNote, Pill } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { ProfileVersion, RunPayload } from "@/lib/types";

/**
 * The only role that can approve. Approval records review of one profile
 * version and carries an optimistic lock, so a stale page cannot approve.
 */
export function ReviewGate({
  profile,
  reviewer,
  onDecided,
}: {
  profile: ProfileVersion;
  reviewer: string | null;
  onDecided: (next: RunPayload) => void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const settled = profile.status !== "pending_review";

  async function decide(decision: "approve" | "reject") {
    setBusy(decision);
    setError(null);
    try {
      const next = await apiPost<RunPayload>(`profile-versions/${profile.id}/decide`, {
        decision,
        reason,
        expected_lock_version: profile.lock_version,
      });
      onDecided(next);
      setReason("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The decision was not recorded.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="stack-sm">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="mono muted" style={{ fontSize: "0.75rem" }}>
          Version {profile.version} · {formatDateTime(profile.created_at)}
        </span>
        <Pill status={profile.status} />
      </div>

      {settled ? (
        <p className="muted" style={{ fontSize: "0.8125rem" }}>
          {profile.status === "approved" ? "Approved" : "Rejected"} by{" "}
          {profile.reviewed_by ?? "a named reviewer"}
          {profile.review_reason ? ` — ${profile.review_reason}` : "."}
        </p>
      ) : !reviewer ? (
        <p className="muted" style={{ fontSize: "0.8125rem" }}>
          Set <code className="mono">PORTFOLIO_REVIEWER_NAME</code> before a decision can be
          recorded.
        </p>
      ) : (
        <>
          <p className="muted" style={{ fontSize: "0.8125rem" }}>
            Approval records that <strong>{reviewer}</strong> reviewed this version. It does not
            convert held or contradicted evidence into supported evidence.
          </p>
          <div className="field">
            <label htmlFor="review-reason">Rationale</label>
            <textarea
              id="review-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={5}
              maxLength={2000}
              placeholder="Why is this version acceptable, or why is it not?"
            />
          </div>
          <div className="row">
            <button
              type="button"
              className="btn"
              data-variant="primary"
              disabled={busy !== null || reason.trim().length < 5}
              onClick={() => decide("approve")}
            >
              {busy === "approve" ? "Recording…" : "Approve version"}
            </button>
            <button
              type="button"
              className="btn"
              data-variant="danger"
              disabled={busy !== null || reason.trim().length < 5}
              onClick={() => decide("reject")}
            >
              {busy === "reject" ? "Recording…" : "Reject"}
            </button>
          </div>
        </>
      )}

      <dl className="kv" style={{ fontSize: "0.75rem" }}>
        <dt>Content SHA-256</dt>
        <dd className="hash">{profile.content_sha256}</dd>
        <dt>Lock version</dt>
        <dd className="mono">{profile.lock_version}</dd>
      </dl>

      {profile.status === "approved" ? (
        <p className="muted" style={{ fontSize: "0.8125rem" }}>
          This version is locked. Open the run graph to inspect claims, sources, and coverage.
        </p>
      ) : null}

      {error ? <ErrorNote message={error} /> : null}
    </div>
  );
}
