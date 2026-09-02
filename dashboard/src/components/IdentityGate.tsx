"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api";
import { ErrorNote, Pill } from "@/components/ui";
import type { CompanyPayload } from "@/lib/types";

/**
 * Identity is the root of every research case. A structurally valid number is
 * still a submitted claim until a named reviewer accepts it with a rationale.
 */
export function IdentityGate({
  company,
  reviewer,
  onDecided,
}: {
  company: CompanyPayload;
  reviewer: string | null;
  onDecided: (next: CompanyPayload) => void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(path: string, decision: "accept" | "reject") {
    setBusy(`${path}:${decision}`);
    setError(null);
    try {
      const next = await apiPost<CompanyPayload>(path, { decision, reason });
      onDecided(next);
      setReason("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The decision was not recorded.");
    } finally {
      setBusy(null);
    }
  }

  const pendingIdentifiers = company.identifiers.filter((item) => item.state === "pending");
  const pendingDomains = company.domains.filter((item) => item.status === "pending");
  const anyPending = pendingIdentifiers.length > 0 || pendingDomains.length > 0;

  return (
    <div className="stack-sm">
      <ul className="list" style={{ border: "1px solid var(--rule)", borderRadius: "var(--r)" }}>
        {company.identifiers.map((item) => (
          <li key={item.id} style={{ padding: "0.7rem 0.85rem" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="mono" style={{ fontSize: "0.875rem" }}>
                {item.value}
              </span>
              <Pill status={item.state} />
            </div>
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              {item.scheme_label} · submitted as <span className="mono">{item.submitted_value}</span>
            </p>
          </li>
        ))}
        {company.domains.map((item) => (
          <li key={item.id} style={{ padding: "0.7rem 0.85rem" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="mono" style={{ fontSize: "0.875rem" }}>
                {item.domain}
              </span>
              <Pill status={item.status} />
            </div>
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              Self-asserted domain claim. It binds to this company only after a named decision.
            </p>
          </li>
        ))}
      </ul>

      {!anyPending ? (
        <p className="muted" style={{ fontSize: "0.8125rem" }}>
          Every submitted identity claim has a recorded decision.
        </p>
      ) : !reviewer ? (
        <p className="muted" style={{ fontSize: "0.8125rem" }}>
          Set <code className="mono">PORTFOLIO_REVIEWER_NAME</code> before a decision can be
          recorded.
        </p>
      ) : (
        <>
          <div className="field">
            <label htmlFor="identity-reason">Rationale</label>
            <textarea
              id="identity-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={5}
              maxLength={2000}
              placeholder="How was this exact entity confirmed?"
            />
          </div>
          <div className="stack-sm">
            {pendingIdentifiers.map((item) => (
              <div className="row" key={item.id}>
                <span className="mono" style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>
                  {item.value}
                </span>
                <button
                  type="button"
                  className="btn"
                  data-size="sm"
                  data-variant="primary"
                  disabled={busy !== null || reason.trim().length < 5}
                  onClick={() =>
                    void decide(`company-identifiers/${item.id}/decide`, "accept")
                  }
                >
                  Accept identity
                </button>
                <button
                  type="button"
                  className="btn"
                  data-size="sm"
                  data-variant="danger"
                  disabled={busy !== null || reason.trim().length < 5}
                  onClick={() =>
                    void decide(`company-identifiers/${item.id}/decide`, "reject")
                  }
                >
                  Reject
                </button>
              </div>
            ))}
            {pendingDomains.map((item) => (
              <div className="row" key={item.id}>
                <span className="mono" style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>
                  {item.domain}
                </span>
                <button
                  type="button"
                  className="btn"
                  data-size="sm"
                  disabled={busy !== null || reason.trim().length < 5}
                  onClick={() => void decide(`company-domains/${item.id}/decide`, "accept")}
                >
                  Verify domain
                </button>
                <button
                  type="button"
                  className="btn"
                  data-size="sm"
                  data-variant="danger"
                  disabled={busy !== null || reason.trim().length < 5}
                  onClick={() => void decide(`company-domains/${item.id}/decide`, "reject")}
                >
                  Reject
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {error ? <ErrorNote message={error} /> : null}
    </div>
  );
}
