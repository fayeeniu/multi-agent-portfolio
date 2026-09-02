"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { IntakeConsole } from "@/components/IntakeConsole";
import {
  EmptyState,
  ErrorNote,
  LedgerRow,
  Panel,
  Pill,
  Skeleton,
  StatGrid,
} from "@/components/ui";
import { formatDate, formatNumber, statusLabel } from "@/lib/format";
import { useDocumentTitle, useResource } from "@/lib/hooks";
import type { CompaniesPayload } from "@/lib/types";

export default function CompaniesPage() {
  const { data, error, refresh } = useResource<CompaniesPayload>("companies");
  const [query, setQuery] = useState("");
  useDocumentTitle("Companies");

  const filtered = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return data.companies;
    return data.companies.filter((company) => {
      const number = company.identifier?.value ?? "";
      return (
        company.name.toLowerCase().includes(needle) || number.toLowerCase().includes(needle)
      );
    });
  }, [data, query]);

  return (
    <div className="overview">
      <div className="page-head">
      <h1 className="visually-hidden">Companies</h1>
      <p className="page-lede">
        A Companies House number opens a case on its own; a name or a domain never does.
      </p>

      <div className="command-band">
        <Panel title="New company">
          <IntakeConsole onCreated={refresh} />
        </Panel>

        {error ? <ErrorNote message={error.message} /> : null}

        {!data ? (
          <div className="stat-grid" aria-hidden="true">
            {Array.from({ length: 4 }).map((_, index) => (
              <div className="stat-card" key={index}>
                <Skeleton lines={2} />
              </div>
            ))}
          </div>
        ) : (
          <StatGrid
            items={[
              {
                icon: "building",
                label: "Companies",
                value: formatNumber(data.counts.total),
                hint: "Each case starts from one Companies House number",
              },
              {
                icon: "badge-check",
                label: "Identity resolved",
                value: formatNumber(data.counts.resolved),
                tone: "evidence",
                hint: "Accepted legal entities",
              },
              {
                icon: "hourglass",
                label: "Open decisions",
                value: formatNumber(data.counts.identity_holds),
                tone: data.counts.identity_holds ? "danger" : "muted",
                hint: data.counts.identity_holds
                  ? "Held until a named reviewer accepts the number"
                  : "No identity is waiting",
              },
              {
                icon: "layers",
                label: "With research runs",
                value: formatNumber(data.counts.with_runs),
                hint: "Cases that have at least one persisted run",
              },
            ]}
          />
        )}
      </div>
      </div>

      {!data ? (
        <Panel title="Companies ledger">
          <Skeleton lines={5} />
        </Panel>
      ) : (
        <>

          <Panel
            title="Companies ledger"
            eyebrow={`${data.companies.length} recorded`}
            flush
            aside={
              data.companies.length > 8 ? (
                <label className="ledger-filter">
                  <span className="visually-hidden">Filter companies</span>
                  <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Filter by name or number"
                  />
                </label>
              ) : null
            }
          >
            {filtered.length === 0 ? (
              <EmptyState
                title={query ? "No company matches that filter." : "The ledger is empty."}
                detail={
                  query
                    ? "Clear the filter to see every recorded number."
                    : "Register a Companies House number above to create the first research case."
                }
              />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Company</th>
                      <th scope="col">Number</th>
                      <th scope="col">Identity</th>
                      <th scope="col">Domain</th>
                      <th scope="col">Evidence</th>
                      <th scope="col">Latest run</th>
                      <th scope="col">Next action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((company) => (
                      <LedgerRow key={company.id} href={`/companies/${company.id}`}>
                        <td>
                          <Link href={`/companies/${company.id}`} style={{ fontWeight: 500 }}>
                            {company.name}
                          </Link>
                          <div className="muted" style={{ fontSize: "0.6875rem" }}>
                            {company.classification} · {formatDate(company.created_at)}
                          </div>
                        </td>
                        <td className="mono">{company.identifier?.value ?? "—"}</td>
                        <td>
                          <Pill status={company.resolution_status} />
                          {company.open_decisions > 0 ? (
                            <div
                              className="muted"
                              style={{ fontSize: "0.6875rem", marginTop: "0.2rem" }}
                            >
                              {company.open_decisions} open
                            </div>
                          ) : null}
                        </td>
                        <td className="mono muted">{company.verified_domain ?? "—"}</td>
                        <td className="mono">
                          {company.claim_count > 0 ? `${company.claim_count} claims` : "—"}
                        </td>
                        <td>
                          {company.latest_run ? (
                            <Link href={`/runs/${company.latest_run.id}`}>
                              <Pill status={company.latest_run.status} />
                            </Link>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                        <td>
                          <Link
                            href={company.next_action.href ?? `/companies/${company.id}`}
                            className="ledger-action"
                          >
                            {company.next_action.label}
                          </Link>
                          <div className="muted" style={{ fontSize: "0.6875rem" }}>
                            {statusLabel(company.lifecycle_status)}
                          </div>
                        </td>
                      </LedgerRow>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
