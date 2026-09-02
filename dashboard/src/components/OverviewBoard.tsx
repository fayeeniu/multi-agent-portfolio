"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { RunPipeline } from "@/components/RunPipeline";
import { EmptyState, LedgerRow, NextActionBanner, Panel, Pill, StatGrid } from "@/components/ui";
import { chartTone, formatNumber, statusLabel } from "@/lib/format";
import type { OverviewPayload, RunSummary } from "@/lib/types";

function modelRouteLabel(
  route: { model: string; effort: string } | undefined,
  fallbackModel: string,
  fallbackEffort: string,
): string {
  return `${route?.model ?? fallbackModel} · ${route?.effort ?? fallbackEffort}`;
}

function sourceProgress(run: RunSummary): number {
  const total = run.sources.total || 0;
  const done = run.sources.fetched ?? 0;
  if (!total) return 0;
  return Math.round((done / total) * 100);
}

function runMix(runs: RunSummary[]) {
  const buckets = { complete: 0, review: 0, active: 0, failed: 0 };
  for (const item of runs) {
    if (item.status === "failed") buckets.failed += 1;
    else if (item.status === "pending_review" || item.status === "awaiting") buckets.review += 1;
    else if (item.status === "running" || item.status === "pending") buckets.active += 1;
    else if (item.status === "succeeded" || item.status === "approved") buckets.complete += 1;
  }
  return buckets;
}

export function OverviewBoard({
  data,
  reduced,
  loading = false,
  fixture = false,
}: {
  data: OverviewPayload;
  reduced: boolean;
  loading?: boolean;
  fixture?: boolean;
}) {
  const { metrics, system } = data;
  const recentRuns = data.runs.slice(0, 4);
  const mix = runMix(data.runs);
  const mixTotal = mix.complete + mix.review + mix.active + mix.failed;
  const settled = mixTotal ? Math.round((mix.complete / mixTotal) * 100) : 0;

  return (
    <div className="overview">
      <div className="page-head">
      {fixture ? (
        <p className="fixture-banner" role="status">
          <span>Static fixture — this page does not call the research service.</span>
          <Link href="/">Open live overview</Link>
        </p>
      ) : null}

      <h1 className="visually-hidden">Overview</h1>
      <p className="page-lede">
        {formatNumber(metrics.companies)} companies · {formatNumber(metrics.claims)} claims ·{" "}
        {formatNumber(metrics.sources_captured)} sources captured
      </p>

      <div className="command-band">
        <NextActionBanner
          size="hero"
          label={data.next_action.label}
          detail={data.next_action.detail}
          href={data.next_action.href}
        />
        <StatGrid
          items={[
            {
              icon: "identity-hold",
              label: "Identity holds",
              value: formatNumber(metrics.identity_holds),
              tone: metrics.identity_holds ? "danger" : "muted",
              hint: metrics.identity_holds
                ? "Nothing collects evidence until these are accepted"
                : "All recorded identities are accepted",
            },
            {
              icon: "activity",
              label: "Runs executing",
              value: formatNumber(metrics.runs_active),
              tone: metrics.runs_active ? "active" : "muted",
              hint: metrics.runs_active ? "Persisted stages still in flight" : "No run is executing",
            },
            {
              icon: "review",
              label: "Awaiting review",
              value: formatNumber(metrics.runs_pending_review),
              tone: metrics.runs_pending_review ? "human" : "muted",
              hint: metrics.runs_pending_review
                ? "Named approval is the only completion gate"
                : "No profile is waiting on a person",
            },
            {
              icon: "withheld",
              label: "Sources withheld",
              value: formatNumber(metrics.sources_withheld),
              tone: metrics.sources_withheld ? "danger" : "muted",
              hint: metrics.sources_withheld
                ? "Blocked, failed or unsupported — absent from evidence"
                : "No captured source was withheld",
            },
          ]}
        />
      </div>
      </div>

      <div className="overview-grid">
        <div className="overview-main">
          <section className="stack-sm">
            <div className="section-head">
              <h2>Needs attention</h2>
              <span className="caption">
                {data.attention.length ? "Blockers first" : "Clear"}
              </span>
            </div>
            {data.attention.length === 0 ? (
              <div className="rail-panel">
                <EmptyState
                  title="Nothing is held, contradicted or failing."
                  detail="Holds, blocked sources, failures and pending reviews appear here in severity order."
                />
              </div>
            ) : (
              <div className="plan-list">
                {data.attention.map((item, index) => (
                  <motion.div
                    key={item.id}
                    initial={reduced ? false : { opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.24, delay: reduced ? 0 : index * 0.02 }}
                  >
                    <Link href={item.href} className="plan-row" data-severity={item.severity}>
                      <span className="plan-mark">{item.kind}</span>
                      <span className="plan-copy">
                        <strong>{item.title}</strong>
                        <span className="caption">
                          {item.detail}
                        </span>
                      </span>
                      <span className="plan-action">
                        {item.action_label} →
                      </span>
                    </Link>
                  </motion.div>
                ))}
              </div>
            )}
          </section>

          <section className="stack-sm">
            <div className="section-head">
              <h2>Recent cases</h2>
              <Link href="/companies">View all</Link>
            </div>
            {recentRuns.length === 0 ? (
              <div className="rail-panel">
                <EmptyState
                  title="No research run has been recorded."
                  detail="Register a Companies House number, accept the identity, then start a bounded public research run."
                />
              </div>
            ) : (
              <div className="case-grid">
                {recentRuns.map((item) => {
                  const progress = sourceProgress(item);
                  return (
                    <Link key={item.id} href={`/runs/${item.id}`} className="case-card">
                      <span className="case-card-copy">
                        <span className="case-card-title">
                          <strong>{item.company_name}</strong>
                          <Pill status={item.status} />
                        </span>
                        <span className="caption">
                          {item.sources.fetched ?? 0}/{item.sources.total} sources · {item.claim_count}{" "}
                          claims
                          {item.active_role ? ` · ${item.active_role}` : ""}
                        </span>
                      </span>
                      <span
                        className="coverage-ring"
                        data-size="sm"
                        data-tone={chartTone(item.status)}
                        style={{ ["--coverage" as string]: `${progress}%` }}
                        aria-label={`${progress}% of sources captured`}
                      >
                        <strong>{progress}%</strong>
                        <span>captured</span>
                      </span>
                      <RunPipeline run={item} />
                    </Link>
                  );
                })}
              </div>
            )}
          </section>

          <Panel
            title="Company ledger"
            eyebrow={`${data.companies.length} recorded`}
            flush
            aside={
              <Link href="/companies">View all</Link>
            }
          >
            {data.companies.length === 0 ? (
              <EmptyState
                title="No company has been registered."
                detail="A Companies House number alone is enough to open a research case."
              />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Company</th>
                      <th scope="col">Number</th>
                      <th scope="col">Identity</th>
                      <th scope="col">Claims</th>
                      <th scope="col">Latest run</th>
                      <th scope="col">Next action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.companies.slice(0, 8).map((row) => (
                      <LedgerRow key={row.id} href={`/companies/${row.id}`}>
                        <td>
                          <Link href={`/companies/${row.id}`} style={{ fontWeight: 500 }}>
                            {row.name}
                          </Link>
                        </td>
                        <td className="mono">{row.identifier?.value ?? "—"}</td>
                        <td>
                          <Pill status={row.resolution_status} />
                        </td>
                        <td className="mono">{row.claim_count}</td>
                        <td>
                          {row.latest_run ? (
                            <Link href={`/runs/${row.latest_run.id}`} className="mono">
                              {statusLabel(row.latest_run.status)}
                            </Link>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                        <td>
                          <Link
                            href={row.next_action.href ?? `/companies/${row.id}`}
                            className="ledger-action"
                          >
                            {row.next_action.label}
                          </Link>
                        </td>
                      </LedgerRow>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <aside className="overview-rail" aria-label="Status and runtime">
          <section className="rail-panel">
            <h2>Overall progress</h2>
            {mixTotal === 0 ? (
              <p className="muted" style={{ fontSize: "0.8125rem" }}>
                No runs recorded yet.
              </p>
            ) : (
              <>
                <div className="progress-block">
                  <span
                    className="coverage-ring"
                    data-mix
                    data-tone="evidence"
                    style={{
                      ["--coverage" as string]: `${settled}%`,
                      ["--mix-a" as string]: `${(mix.complete / mixTotal) * 100}%`,
                      ["--mix-b" as string]: `${((mix.complete + mix.review) / mixTotal) * 100}%`,
                      ["--mix-c" as string]: `${((mix.complete + mix.review + mix.active) / mixTotal) * 100}%`,
                    }}
                    aria-label={`${settled}% of recorded runs are complete`}
                  >
                    <strong>{settled}%</strong>
                    <span>complete</span>
                  </span>
                  <div className="mix-legend" style={{ gridTemplateColumns: "1fr", marginTop: 0 }}>
                    <span data-tone="evidence">
                      Complete <b>{mix.complete}</b>
                    </span>
                    <span data-tone="human">
                      Review <b>{mix.review}</b>
                    </span>
                    <span data-tone="active">
                      Active <b>{mix.active}</b>
                    </span>
                    <span data-tone="danger">
                      Failed <b>{mix.failed}</b>
                    </span>
                  </div>
                </div>
                <div className="mix-bar" aria-hidden="true">
                  {mix.complete ? (
                    <i data-tone="evidence" style={{ width: `${(mix.complete / mixTotal) * 100}%` }} />
                  ) : null}
                  {mix.review ? (
                    <i data-tone="human" style={{ width: `${(mix.review / mixTotal) * 100}%` }} />
                  ) : null}
                  {mix.active ? (
                    <i data-tone="active" style={{ width: `${(mix.active / mixTotal) * 100}%` }} />
                  ) : null}
                  {mix.failed ? (
                    <i data-tone="danger" style={{ width: `${(mix.failed / mixTotal) * 100}%` }} />
                  ) : null}
                </div>
              </>
            )}
          </section>

          <section className="rail-panel">
            <h2>Runtime</h2>
            <dl className="kv">
              <dt>Runtime</dt>
              <dd>{system.runtime}</dd>
              <dt>Reviewer</dt>
              <dd>{system.reviewer ?? "Not configured"}</dd>
              <dt>Reasoning</dt>
              <dd className="mono">
                {system.external_model_enabled
                  ? modelRouteLabel(system.model_route?.reasoning, system.escalation_model, "configured")
                  : "Closed by default"}
              </dd>
              <dt>Live retrieval</dt>
              <dd>{system.live_retrieval_enabled ? "Open" : "Closed"}</dd>
              <dt>Export</dt>
              <dd>Named approval required</dd>
            </dl>
            <p className="caption" style={{ marginTop: "var(--space-4)" }}>
              {system.boundary}
            </p>
          </section>

          <section className="rail-panel roster-panel">
            <h2>Agent roster</h2>
            <div className="roster-compact">
              {system.agents.map((agent) => (
                <div key={agent.key} className="roster-compact-row">
                  <div>
                    <h3>{agent.label}</h3>
                    <p className="muted" style={{ fontSize: "0.6875rem" }}>
                      {agent.layer}
                    </p>
                  </div>
                  <span className="gnode-engine" data-engine={agent.engine}>
                    {agent.engine === "model" ? "model" : agent.engine === "human" ? "human" : "code"}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>

      {loading ? <span className="visually-hidden">Refreshing control room state</span> : null}
    </div>
  );
}
