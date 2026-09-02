"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import { ClaimLedger } from "@/components/ClaimLedger";
import { IdentityGate } from "@/components/IdentityGate";
import { InvestmentBrief, claimsForCategories } from "@/components/InvestmentBrief";
import { PortfolioMetrics } from "@/components/PortfolioMetrics";
import { RunPipeline } from "@/components/RunPipeline";
import {
  BoardSkeleton,
  EmptyState,
  ErrorNote,
  NextActionBanner,
  Panel,
  Pill,
  ServiceError,
  StatGrid,
} from "@/components/ui";
import { ApiError, apiPost } from "@/lib/api";
import { formatDate, formatDateTime, formatNumber, humanize, shortHash } from "@/lib/format";
import { useDocumentTitle, useResource } from "@/lib/hooks";
import type { CompanyPayload, RunPayload, SessionPayload } from "@/lib/types";

export default function CompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const session = useResource<SessionPayload>("session");
  const company = useResource<CompanyPayload>(`companies/${id}`);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  useDocumentTitle(company.data?.company.name ?? "Company");

  if (company.error) {
    return (
      <ServiceError
        title="This company could not be loaded."
        message={company.error.message}
        onRetry={() => void company.refresh()}
      />
    );
  }

  if (!company.data) {
    return <BoardSkeleton />;
  }

  const data = company.data;
  const primary = data.identifiers.find((item) => item.scheme === "companies_house_number");
  const resolved = data.company.resolution_status === "resolved";
  const openCase = data.cases[0] ?? null;
  const claims = data.sections.flatMap((section) => section.claims);
  const companyClaims = claimsForCategories(data, ["identity", "products_market"]);
  const financeClaims = claimsForCategories(data, [
    "funding",
    "performance",
    "awards",
    "corporate_actions",
  ]);
  const riskClaims = claimsForCategories(data, ["challenges", "regulation", "public_discourse"]);
  const captured = data.lanes.filter((lane) => lane.status === "fetched").length;
  const investmentReport = data.investment_report ?? null;

  async function startRun() {
    if (!openCase) return;
    setStarting(true);
    setStartError(null);
    try {
      const run = await apiPost<RunPayload>(`research-cases/${openCase.id}/runs`, {});
      router.push(`/runs/${run.run.id}`);
    } catch (caught) {
      setStartError(caught instanceof ApiError ? caught.message : "The run could not be created.");
      setStarting(false);
    }
  }

  return (
    <div className="overview">
      <nav className="crumb">
        <Link href="/">Overview</Link>
        <span aria-hidden="true">/</span>
        <Link href="/companies">Companies</Link>
        <span aria-hidden="true">/</span>
        <span className="mono">{primary?.value ?? data.company.id}</span>
      </nav>

      <section className="overview-hero stack-sm">
        <div className="row" style={{ gap: "0.7rem" }}>
          <h1 className="page-title">{data.company.name}</h1>
          <Pill status={data.company.resolution_status} />
        </div>
        <p className="lede page-lede">
          Number {primary?.value ?? "not recorded"} · {data.company.classification} ·{" "}
          {data.company.jurisdiction ?? "jurisdiction not recorded"} · registered{" "}
          {formatDate(data.company.created_at)}.
        </p>
      </section>

      {startError ? <ErrorNote message={startError} /> : null}

      <div className="command-band">
        <NextActionBanner
          size="hero"
          label={data.next_action.label}
          detail={data.next_action.detail}
          href={
            /start/i.test(data.next_action.label)
              ? null
              : (data.next_action.href ??
                (data.runs[0] ? `/runs/${data.runs[0].id}` : "#identity"))
          }
          action={
            /start/i.test(data.next_action.label) &&
            resolved &&
            openCase &&
            data.live_research_enabled ? (
              <button
                type="button"
                className="btn"
                data-variant="primary"
                disabled={starting}
                onClick={() => void startRun()}
              >
                {starting ? "Creating run…" : "Start run"}
              </button>
            ) : undefined
          }
        />

        <StatGrid
          items={[
            {
              icon: "activity",
              label: "Research runs",
              value: formatNumber(data.runs.length),
              hint: "Each run pins one cutoff and one source policy",
            },
            {
              icon: "quote",
              label: "Claims admitted",
              value: formatNumber(claims.length),
              tone: claims.length ? "evidence" : "muted",
              hint: "Statements that passed admission",
            },
            {
              icon: "inbox",
              label: "Sources captured",
              value: formatNumber(captured),
              hint: `${data.lanes.length} planned lanes`,
            },
            {
              icon: "versions",
              label: "Profile versions",
              value: formatNumber(data.profile_versions.length),
              tone: data.profile?.status === "approved" ? "evidence" : "human",
              hint: data.profile ? humanize(data.profile.status) : "No composed version yet",
            },
          ]}
        />
      </div>

      <div className="run-controls">
        {data.runs[0] ? (
          <Link className="btn" href={`/runs/${data.runs[0].id}`}>
            Open run
          </Link>
        ) : null}
        <Link className="btn" href="/reports">
          Reports
        </Link>
      </div>

      <nav className="section-nav" aria-label="Company sections">
        <a href="#assessment">Assessment</a>
        <a href="#portfolio-metrics">Portfolio metrics</a>
        <a href="#company-details">Company details</a>
        <a href="#finance">Finance & scale</a>
        <a href="#risk">Risk & regulation</a>
        <a href="#sources">Sources</a>
        <a href="#reports">Profile versions</a>
      </nav>

      <section id="assessment" className="anchor-section">
        <InvestmentBrief data={data} />
      </section>

      <section id="portfolio-metrics" className="anchor-section">
        <Panel
          title="CBIT portfolio metrics"
          eyebrow={
            investmentReport
              ? `Contract ${investmentReport.metric_contract_version}`
              : "Metric report not generated"
          }
          flush
        >
          {investmentReport ? (
            <PortfolioMetrics report={investmentReport} />
          ) : (
            <EmptyState
              title="This saved profile has no metric report."
              detail="Admitted claims and sources below remain available. Missing report data is not treated as zero evidence."
            />
          )}
        </Panel>
      </section>

      <div className="split">
        <div className="stack">
          <div id="company-details" className="anchor-section">
            <Panel
              title="Company details"
              eyebrow={
                data.profile
                  ? `Version ${data.profile.version} · ${humanize(data.profile.status)}`
                  : "No version yet"
              }
              flush
            >
            {companyClaims.length === 0 ? (
              <EmptyState
                title="No company or market evidence has been admitted."
                detail={
                  resolved
                    ? "Start a bounded research run. Every statement that appears here will carry the exact source span that admitted it."
                    : "Accept the exact identity first. Collection cannot start while identity is held."
                }
              />
            ) : (
              <ClaimLedger claims={companyClaims} lanes={data.lanes} />
            )}
            </Panel>
          </div>

          <div id="finance" className="anchor-section">
            <Panel title="Finance & scale" eyebrow={`${financeClaims.length} admitted claims`} flush>
              {financeClaims.length ? (
                <ClaimLedger claims={financeClaims} lanes={data.lanes} />
              ) : (
                <EmptyState
                  title="Financial evidence is incomplete."
                  detail="No filing, funding, grant or reported-performance span has passed admission. The dashboard does not infer financial strength from missing data."
                />
              )}
            </Panel>
          </div>

          <div id="risk" className="anchor-section">
            <Panel title="Risk, regulation & public record" eyebrow={`${riskClaims.length} admitted claims`} flush>
              {riskClaims.length ? (
                <ClaimLedger claims={riskClaims} lanes={data.lanes} />
              ) : (
                <EmptyState
                  title="No risk evidence has been admitted."
                  detail="This is an evidence gap, not evidence that the company has no material risks."
                />
              )}
            </Panel>
          </div>

          <Panel title="Research runs" eyebrow="Execution history" flush>
            {data.runs.length === 0 ? (
              <EmptyState
                title="No run has been recorded."
                detail="A run pins one cutoff, one source policy version and one budget envelope."
              />
            ) : (
              <ul className="list">
                {data.runs.map((run) => (
                  <li key={run.id}>
                    <Link href={`/runs/${run.id}`} className="rowlink" style={{ gap: "0.45rem" }}>
                      <span className="row" style={{ justifyContent: "space-between" }}>
                        <span className="row" style={{ gap: "0.6rem" }}>
                          <span className="mono" style={{ fontSize: "0.75rem" }}>
                            cutoff {formatDate(run.cutoff)}
                          </span>
                          <Pill status={run.status} />
                        </span>
                        <span className="mono muted" style={{ fontSize: "0.6875rem" }}>
                          {formatDateTime(run.created_at)}
                        </span>
                      </span>
                      <RunPipeline run={run} />
                      <span className="row muted" style={{ gap: "1rem", fontSize: "0.6875rem" }}>
                        <span>
                          {run.sources.fetched ?? 0}/{run.sources.total} sources
                        </span>
                        <span>{run.claim_count} claims</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="stack" id="identity">
          <Panel
            title="Identity"
            eyebrow="Root of the case"
            aside={<Pill status={data.company.resolution_status} />}
          >
            <IdentityGate
              company={data}
              reviewer={session.data?.system.reviewer ?? null}
              onDecided={(next) => company.set(next)}
            />
          </Panel>

          <Panel title="Research case" eyebrow="Scope">
            {openCase ? (
              <dl className="kv">
                <dt>Purpose</dt>
                <dd>{openCase.purpose}</dd>
                <dt>Classification</dt>
                <dd>{humanize(openCase.classification)}</dd>
                <dt>Status</dt>
                <dd>{humanize(openCase.status)}</dd>
                <dt>Opened by</dt>
                <dd>{openCase.created_by}</dd>
              </dl>
            ) : (
              <p className="muted" style={{ fontSize: "0.8125rem" }}>
                No research case exists for this company.
              </p>
            )}
            {!data.live_research_enabled ? (
              <p className="muted" style={{ fontSize: "0.75rem", marginTop: "0.7rem" }}>
                Live research is closed. Set a reviewer and enable public retrieval and the model
                on the service, then restart it.
              </p>
            ) : null}
          </Panel>

          <div id="reports" className="anchor-section">
            <Panel title="Profile versions" eyebrow="Named review">
              {data.profile ? (
                <div className="stack-sm">
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <span>Profile version {data.profile.version}</span>
                    <Pill status={data.profile.status} />
                  </div>
                  <p className="muted" style={{ fontSize: "0.75rem" }}>
                    The profile is composed from admitted claims. A named reviewer must approve or
                    reject this exact version.
                  </p>
                  {data.runs[0] ? (
                    <Link className="btn" data-size="sm" href={`/runs/${data.runs[0].id}`}>
                      {data.profile.status === "pending_review" ? "Open review gate" : "Open run"}
                    </Link>
                  ) : (
                    <p className="muted" style={{ fontSize: "0.75rem" }}>
                      No run is available to review yet.
                    </p>
                  )}
                </div>
              ) : (
                <EmptyState title="No profile version exists." detail="Run research through composition to create the first reviewable profile." />
              )}
            </Panel>
          </div>

          <div id="sources" className="anchor-section">
            <Panel title="Source coverage" eyebrow={`${data.lanes.length} candidates`} flush>
              {data.lanes.length ? (
                <ul className="list">
                  {data.lanes.map((lane) => (
                    <li key={lane.id} style={{ padding: "0.7rem 1rem" }}>
                      <div className="row" style={{ justifyContent: "space-between" }}>
                        <a href={lane.url} target="_blank" rel="noreferrer noopener" style={{ fontSize: "0.75rem", overflowWrap: "anywhere" }}>
                          {lane.title ?? lane.publisher_domain}
                        </a>
                        <Pill status={lane.status} />
                      </div>
                      <p className="mono muted" style={{ fontSize: "0.625rem" }}>
                        {lane.source_tier_label} · {lane.claim_count} admitted claims
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No sources recorded." detail="Source candidates appear after planning succeeds." />
              )}
            </Panel>
          </div>

          <Panel title="Intake artifacts" eyebrow="Immutable record" flush>
            {data.artifacts.length === 0 ? (
              <div className="empty">No intake artifact is recorded.</div>
            ) : (
              <ul className="list">
                {data.artifacts.map((artifact) => (
                  <li key={artifact.id} style={{ padding: "0.7rem 1.1rem" }}>
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <span style={{ fontSize: "0.8125rem" }}>{artifact.kind_label}</span>
                      <span className="mono muted" style={{ fontSize: "0.625rem" }}>
                        {artifact.classification}
                      </span>
                    </div>
                    <p className="mono muted" style={{ fontSize: "0.6875rem" }}>
                      {artifact.normalized_value ?? artifact.original_filename ?? "—"}
                    </p>
                    <p className="hash">{shortHash(artifact.content_sha256, 24)}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
