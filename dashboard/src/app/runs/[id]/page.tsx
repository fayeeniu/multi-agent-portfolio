"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useRef, useState } from "react";
import { AgentGraph } from "@/components/AgentGraph";
import { ClaimLedger } from "@/components/ClaimLedger";
import { Inspector, type InspectorSelection } from "@/components/Inspector";
import { ReviewGate } from "@/components/ReviewGate";
import { BoardSkeleton, EmptyState, ErrorNote, NextActionBanner, Panel, Pill, ServiceError, StatGrid } from "@/components/ui";
import { ApiError, apiPost } from "@/lib/api";
import { formatDate, formatDuration, humanize } from "@/lib/format";
import { useDocumentTitle, useElapsed, useResource } from "@/lib/hooks";
import type { GraphNode, RunPayload, SessionPayload } from "@/lib/types";

const ACTIVE_STATUSES = new Set(["pending", "running"]);
const RESTARTABLE_STATUSES = new Set(["approved", "rejected", "failed", "cancelled"]);

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [selection, setSelection] = useState<InspectorSelection>(null);
  const [inflight, setInflight] = useState<{ capability: string; since: number } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [autoStatus, setAutoStatus] = useState<string | null>(null);
  const [autoRun, setAutoRun] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const abort = useRef(false);

  const session = useResource<SessionPayload>("session");
  const active = inflight !== null;
  const run = useResource<RunPayload>(`research-runs/${id}`, active ? 1500 : 0);
  const payload = run.data;

  const elapsed = useElapsed(inflight !== null, inflight?.since ?? null);

  const advance = useCallback(async (showStageError = true): Promise<RunPayload | null> => {
    if (!payload) return null;
    const capability =
      payload.nodes.find(
        (node) => node.kind === "task" && (node.status === "pending" || node.status === "failed"),
      )?.id ?? "";
    setInflight({ capability, since: Date.now() });
    setActionError(null);
    try {
      const next = await apiPost<RunPayload>(`research-runs/${id}/advance`, {});
      run.set(next);
      if (next.advance && !next.advance.ok) {
        if (showStageError) {
          setActionError(next.advance.message ?? "The stage recorded a failure.");
        }
      }
      return next;
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "The stage could not run.");
      return null;
    } finally {
      setInflight(null);
    }
  }, [id, payload, run]);

  const runToReview = useCallback(async () => {
    abort.current = false;
    setAutoRun(true);
    setAutoStatus("Starting the next persisted stage.");
    try {
      for (let step = 0; step < 12; step += 1) {
        if (abort.current) break;
        const next = await advance(false);
        if (!next) break;
        if (next.advance && !next.advance.ok) {
          if (next.advance.retryable) {
            setAutoStatus(
              `${humanize(next.advance.capability)} attempt was rejected; retrying automatically ` +
                `with ${next.advance.attempts_remaining} attempt remaining.`,
            );
            continue;
          }
          setActionError(next.advance.message ?? "The stage recorded a non-retryable failure.");
          break;
        }
        setAutoStatus(
          next.advance?.capability
            ? `${humanize(next.advance.capability)} completed. Continuing to the next stage.`
            : "Stage completed. Continuing.",
        );
        if (!ACTIVE_STATUSES.has(next.run.status)) break;
      }
    } finally {
      setAutoRun(false);
      setAutoStatus(null);
    }
  }, [advance]);

  const restartFromStageOne = useCallback(async () => {
    setRestarting(true);
    setActionError(null);
    try {
      const next = await apiPost<RunPayload>(`research-runs/${id}/restart`, {});
      router.push(`/runs/${next.run.id}`);
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "A fresh run could not be created.",
      );
      setRestarting(false);
    }
  }, [id, router]);

  useDocumentTitle(payload ? `${payload.run.company_name} · Run` : "Research run");

  if (run.error) {
    return (
      <ServiceError
        title="This research run could not be loaded."
        message={run.error.message}
        onRetry={() => void run.refresh()}
      />
    );
  }

  if (!payload) {
    return <BoardSkeleton />;
  }

  const { run: meta } = payload;
  const nodes: GraphNode[] = payload.nodes.map((node) =>
    inflight && node.id === inflight.capability && node.status !== "running"
      ? { ...node, status: "running", detail: "Executing now. The stage holds an exclusive claim." }
      : node,
  );
  const runnable = ACTIVE_STATUSES.has(meta.status);
  const restartable = RESTARTABLE_STATUSES.has(meta.status);
  const busy = inflight !== null || autoRun || restarting;
  const highlightSource = selection?.kind === "lane" ? selection.id : null;

  const captured = payload.lanes.filter((lane) => lane.status === "fetched").length;
  const withheld = payload.lanes.filter((lane) =>
    lane.status === "blocked" || lane.status === "failed" || lane.status === "unsupported",
  ).length;

  return (
    <div className="overview">
      <div className="page-head">
      <nav className="crumb">
        <Link href="/">Overview</Link>
        <span aria-hidden="true">/</span>
        <Link href={`/companies/${meta.company_id}`}>{meta.company_name}</Link>
        <span aria-hidden="true">/</span>
        <span>Run</span>
      </nav>

      <section className="overview-hero stack-sm">
        <p className="overview-kicker">
          Research run · {meta.company_number ?? "no number"}
        </p>
        <div className="row" style={{ gap: "var(--space-3)" }}>
          <h1 className="page-title">{meta.company_name}</h1>
          <Pill status={meta.status} />
        </div>
        <p className="page-lede">
          Cutoff {formatDate(meta.cutoff)}. Routed through {meta.model}. Started by {meta.created_by}.
        </p>
      </section>

      <div className="command-band">
        <NextActionBanner
          size="hero"
          label={payload.next_action.label}
          detail={payload.next_action.detail}
          href={payload.next_action.href}
        />

      <StatGrid
        items={[
          {
            icon: "inbox",
            label: "Sources captured",
            value: captured,
            tone: captured ? "evidence" : "muted",
            hint: `${payload.lanes.length} planned lanes`,
          },
          {
            icon: "withheld",
            label: "Sources withheld",
            value: withheld,
            tone: withheld ? "danger" : "muted",
            hint: withheld ? "Blocked, failed or unsupported — not in evidence" : "No captured source was withheld",
          },
          {
            icon: "compare",
            label: "Contradictions",
            value: payload.contradictions.length,
            tone: payload.contradictions.length ? "human" : "muted",
            hint: payload.contradictions.length
              ? "Neither value enters the supported summary"
              : "No conflicting admitted statements",
          },
          {
            icon: "quote",
            label: "Claims admitted",
            value: payload.claims.length,
            tone: payload.claims.length ? "evidence" : "muted",
            hint: "Exact-span statements that passed admission",
          },
        ]}
      />
      </div>
      </div>

      <div className="run-controls">
        {runnable ? (
          <>
            <button
              type="button"
              className="btn"
              data-variant="primary"
              disabled={busy}
              onClick={() => void runToReview()}
            >
              {autoRun ? "Running…" : "Run to review"}
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => void advance(true)}>
              {inflight && !autoRun ? "Executing…" : "Advance one stage"}
            </button>
            {autoRun ? (
              <button
                type="button"
                className="btn"
                data-variant="danger"
                onClick={() => {
                  abort.current = true;
                }}
              >
                Stop after this stage
              </button>
            ) : null}
          </>
        ) : null}
        {restartable ? (
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void restartFromStageOne()}
          >
            {restarting ? "Creating fresh run…" : "Restart from stage one"}
          </button>
        ) : null}
        <button type="button" className="btn" data-size="sm" onClick={() => void run.refresh()}>
          Refresh
        </button>
      </div>

      {actionError ? <ErrorNote message={actionError} /> : null}

      {autoStatus ? (
        <div className="run-notice" role="status" aria-live="polite">
          <span className="run-notice-dot" aria-hidden="true" />
          {autoStatus}
        </div>
      ) : null}

      {inflight ? (
        <p className="mono" style={{ fontSize: "0.75rem", color: "var(--evidence)" }}>
          Executing {humanize(inflight.capability)} — the stage holds an exclusive claim on this
          run. Elapsed {formatDuration(elapsed)}.
        </p>
      ) : null}

      <section className="stack-sm execution-block">
        <div className="section-head execution-figure">
          <h2>Execution</h2>
          <span className="execution-figure-meta">{payload.lanes.length} source lanes</span>
        </div>
        <AgentGraph
          nodes={nodes}
          lanes={payload.lanes}
          selection={selection}
          onSelect={setSelection}
          runningSince={inflight?.since ?? null}
        />
      </section>

      <div className="overview-grid">
        <div className="overview-main">
          {payload.contradictions.length > 0 ? (
            <section className="stack-sm">
              <div className="section-head">
                <h2>Needs attention</h2>
                <Pill tone="human" label={`${payload.contradictions.length} contradictions`} />
              </div>
              <div className="plan-list" style={{ gridTemplateColumns: "minmax(0, 1fr)" }}>
                {payload.contradictions.map((item) => (
                  <div className="contradiction-card" key={`${item.category}-${item.subject_key}`}>
                    <div className="row">
                      <span className="eyebrow">{humanize(item.category)}</span>
                      <span className="mono muted" style={{ fontSize: "0.6875rem" }}>
                        {item.subject_key}
                      </span>
                    </div>
                    <p className="muted" style={{ fontSize: "0.8125rem" }}>
                      Different sources state different things about the same subject. Neither value
                      enters the supported summary.
                    </p>
                    <ul className="contradiction-claims">
                      {item.claims.map((claim, index) => (
                        <li key={index}>
                          {claim.statement}
                          <div className="mono muted" style={{ fontSize: "0.625rem", marginTop: "0.2rem" }}>
                            {claim.source_url}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <Panel
            title={highlightSource ? "Claims from the selected source" : "Claim and evidence ledger"}
            eyebrow={`${payload.claims.length} admitted`}
            flush
            aside={
              highlightSource ? (
                <button
                  type="button"
                  className="btn"
                  data-size="sm"
                  onClick={() => setSelection(null)}
                >
                  Clear filter
                </button>
              ) : null
            }
          >
            <ClaimLedger
              claims={payload.claims}
              lanes={payload.lanes}
              highlightSourceId={highlightSource}
            />
          </Panel>

          {payload.profile ? (
            <Panel title="Human review gate" eyebrow="Named decision">
              <ReviewGate
                profile={payload.profile}
                reviewer={session.data?.system.reviewer ?? null}
                onDecided={(next) => run.set(next)}
              />
            </Panel>
          ) : (
            <Panel title="Human review gate" eyebrow="Named decision">
              <EmptyState
                title="No profile version exists yet."
                detail="Composition creates one pending-review version. Named approval is required before the profile is locked."
              />
            </Panel>
          )}
        </div>

        <aside className="overview-rail">
          <Inspector payload={payload} selection={selection} />
        </aside>
      </div>
    </div>
  );
}
