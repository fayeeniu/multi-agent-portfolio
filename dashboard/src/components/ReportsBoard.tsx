"use client";

import Link from "next/link";
import { EmptyState, NextActionBanner, Pill, StatGrid } from "@/components/ui";
import { chartTone, formatDate, formatNumber, humanize, shortHash } from "@/lib/format";
import type { OverviewPayload, RunSummary } from "@/lib/types";

const FLOW = [
  ["01", "Discover", "Public-source bucket"],
  ["02", "Capture", "Policy-checked snapshots"],
  ["03", "Select", "Exact-span claims"],
  ["04", "Map", "CBIT metric boundaries"],
  ["05", "Compose", "Versioned proposal"],
  ["06", "Review", "Named approval"],
] as const;

function sourceProgress(run: RunSummary): number {
  const total = run.sources.total || 0;
  const done = run.sources.fetched ?? 0;
  if (!total) return 0;
  return Math.round((done / total) * 100);
}

export function ReportsBoard({
  data,
  fixture = false,
}: {
  data: OverviewPayload;
  fixture?: boolean;
}) {
  const reportRuns = data.runs.filter((run) => run.profile !== null);
  const approved = reportRuns.filter((run) => run.profile?.status === "approved");
  const review = reportRuns.filter((run) => run.profile?.status === "pending_review");
  const claims = reportRuns.reduce((sum, run) => sum + run.claim_count, 0);
  const sources = reportRuns.reduce((sum, run) => sum + (run.sources.fetched ?? 0), 0);
  const nextReview = review[0];

  const nextAction = nextReview
    ? {
        label: `Review ${review.length} profile version${review.length === 1 ? "" : "s"}`,
        detail: "A completed run is waiting on the only role that can approve.",
        href: `/runs/${nextReview.id}`,
      }
    : {
        label: "Start a research run",
        detail: "Profiles appear here after composition.",
        href: "/companies",
      };

  return (
    <div className="overview">
      <div className="page-head">
      {fixture ? (
        <p className="fixture-banner" role="status">
          <span>Static fixture — this page does not call the research service.</span>
          <Link href="/mock">Open Overview mock</Link>
        </p>
      ) : null}

      <h1 className="visually-hidden">Reports</h1>
      <p className="page-lede">
        {formatNumber(sources)} sources captured across versioned profiles.
      </p>

      <div className="command-band">
        <NextActionBanner
          size="hero"
          label={nextAction.label}
          detail={nextAction.detail}
          href={nextAction.href}
        />
        <StatGrid
          items={[
            {
              icon: "review",
              label: "Awaiting review",
              value: formatNumber(review.length),
              tone: review.length ? "human" : "muted",
              hint: review.length ? "A named decision is outstanding" : "No version is waiting",
            },
            {
              icon: "file-check",
              label: "Approved profiles",
              value: formatNumber(approved.length),
              tone: approved.length ? "evidence" : "muted",
              hint: "Locked after a named decision",
            },
            {
              icon: "versions",
              label: "Profile versions",
              value: formatNumber(reportRuns.length),
              hint: "Immutable versions from composed runs",
            },
            {
              icon: "document",
              label: "Claims represented",
              value: formatNumber(claims),
              hint: "Admitted spans across those versions",
            },
          ]}
        />
      </div>
      </div>

      <div className="overview-grid">
        <div className="overview-main">
          <section className="stack-sm">
            <div className="section-head">
              <h2>Run library</h2>
              <Link href="/companies">View companies</Link>
            </div>
            {reportRuns.length === 0 ? (
              <div className="rail-panel">
                <EmptyState
                  title="No profile version exists yet."
                  detail="Complete a research run through composition. The resulting profile will appear here before approval."
                />
              </div>
            ) : (
              <div className="report-library">
                {reportRuns.map((run) => {
                  const profile = run.profile;
                  if (!profile) return null;
                  const ready = profile.status === "approved";
                  const progress = sourceProgress(run);
                  return (
                    <article className="report-card" key={profile.id} data-ready={ready ? "true" : "false"}>
                      <div className="report-card-head">
                        <div className="stack-sm" style={{ gap: "0.35rem", minWidth: 0 }}>
                          <p className="eyebrow">
                            Version {profile.version} · cutoff {formatDate(run.cutoff)}
                          </p>
                          <h2>{run.company_name}</h2>
                          <Pill status={profile.status} />
                        </div>
                        <span
                          className="coverage-ring"
                          data-size="sm"
                          data-tone={ready ? "evidence" : chartTone(profile.status)}
                          style={{ ["--coverage" as string]: `${progress}%` }}
                          aria-label={`${progress}% of sources captured`}
                        >
                          <strong>{progress}%</strong>
                        </span>
                      </div>
                      <dl className="kv">
                        <dt>Claims</dt>
                        <dd>{run.claim_count}</dd>
                        <dt>Captured sources</dt>
                        <dd>
                          {run.sources.fetched ?? 0}/{run.sources.total}
                        </dd>
                        <dt>Content hash</dt>
                        <dd className="hash">{shortHash(profile.content_sha256, 20)}</dd>
                      </dl>
                      <p className="muted" style={{ fontSize: "0.75rem" }}>
                        {ready
                          ? "Named approval is on this exact version."
                          : `${humanize(profile.status)}. Open the run to review claims and sources.`}
                      </p>
                      <div className="row">
                        <Link
                          className="btn"
                          data-variant={ready ? undefined : "primary"}
                          data-size="sm"
                          href={`/runs/${run.id}`}
                        >
                          {ready ? "Open run" : "Review version"}
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        <aside className="overview-rail" aria-label="Research process">
          <section className="rail-panel">
            <h2>How a profile is built</h2>
            <ol className="report-steps">
              {FLOW.map(([step, label, detail]) => (
                <li key={step}>
                  <span>{step}</span>
                  <strong>{label}</strong>
                  <small>{detail}</small>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </div>
  );
}
