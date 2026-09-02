"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Pill } from "@/components/ui";
import {
  formatBytes,
  formatDate,
  formatDateTime,
  formatDuration,
  formatNumber,
  humanize,
  shortModel,
  statusLabel,
} from "@/lib/format";
import { usePrefersReducedMotion } from "@/lib/hooks";
import type { Claim, GraphNode, RunPayload, SourceLane } from "@/lib/types";

export type InspectorSelection =
  | { kind: "node"; id: string }
  | { kind: "lane"; id: string }
  | null;

export function Inspector({
  payload,
  selection,
}: {
  payload: RunPayload;
  selection: InspectorSelection;
}) {
  const reduced = usePrefersReducedMotion();
  const node =
    selection?.kind === "node"
      ? payload.nodes.find((item) => item.id === selection.id) ?? null
      : null;
  const lane =
    selection?.kind === "lane"
      ? payload.lanes.find((item) => item.id === selection.id) ?? null
      : null;
  const key = selection ? `${selection.kind}:${selection.id}` : "run";

  return (
    <div className="inspector">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={key}
          initial={reduced ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? undefined : { opacity: 0, y: -4 }}
          transition={{ duration: 0.2 }}
        >
          {node ? (
            <NodeInspector node={node} />
          ) : lane ? (
            <LaneInspector
              lane={lane}
              claims={payload.claims.filter((claim) => claim.source_id === lane.id)}
            />
          ) : (
            <RunInspector payload={payload} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="inspector-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function NodeInspector({ node }: { node: GraphNode }) {
  return (
    <div className="stack">
      <header className="stack-sm" style={{ gap: "0.35rem" }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <p className="eyebrow">{node.layer} layer</p>
          <Pill status={node.status} />
        </div>
        <h2>{node.label}</h2>
        <p className="muted" style={{ fontSize: "0.8125rem" }}>
          {node.summary}
        </p>
      </header>

      <Section title="Contract">
        <dl className="kv">
          <dt>Owns</dt>
          <dd>{node.contract.owns || "—"}</dd>
          <dt>Must not</dt>
          <dd>{node.contract.must_not || "—"}</dd>
          <dt>Inputs</dt>
          <dd>{node.contract.inputs || "—"}</dd>
          <dt>Outputs</dt>
          <dd>{node.contract.outputs || "—"}</dd>
        </dl>
      </Section>

      {node.outputs_summary.length > 0 ? (
        <Section title="Recorded output">
          <dl className="kv">
            {node.outputs_summary.map((item) => (
              <FragmentRow key={item.label} label={item.label} value={item.value} />
            ))}
          </dl>
        </Section>
      ) : null}

      {node.route ? (
        <Section title="Model routing">
          <dl className="kv">
            <dt>Next attempt</dt>
            <dd className="mono">{node.route.model}</dd>
            <dt>Reasoning effort</dt>
            <dd className="mono">{node.route.effort}</dd>
            <dt>Tier</dt>
            <dd>
              {node.route.tier === "reasoning"
                ? "Reasoning tier — this stage carries the judgement in the run."
                : "Repair tier — a repeat attempt is a mechanical correction."}
            </dd>
          </dl>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            Routing is fixed in code. No model chooses it, and the attempt log below records the
            model that actually ran.
          </p>
        </Section>
      ) : null}

      {node.kind === "task" ? (
        <Section title="Execution record">
          <dl className="kv">
            <dt>Attempts</dt>
            <dd className="mono">
              {node.attempts ? `${node.attempts.count} of ${node.attempts.max}` : "—"}
            </dd>
            <dt>Started</dt>
            <dd>{formatDateTime(node.started_at)}</dd>
            <dt>Finished</dt>
            <dd>{formatDateTime(node.finished_at)}</dd>
            <dt>Duration</dt>
            <dd className="mono">{formatDuration(node.duration_ms)}</dd>
            <dt>Input hash</dt>
            <dd className="hash">{node.input_hash ?? "—"}</dd>
            <dt>Output hash</dt>
            <dd className="hash">{node.output_hash ?? "—"}</dd>
          </dl>
        </Section>
      ) : null}

      {node.attempt_log.length > 0 ? (
        <Section title="Attempt log">
          <ul className="attempt-log">
            {node.attempt_log.map((attempt) => (
              <li key={attempt.attempt} data-status={attempt.status}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="mono">Attempt {attempt.attempt}</span>
                  <Pill status={attempt.status} />
                </div>
                <dl className="kv" style={{ fontSize: "0.75rem" }}>
                  {attempt.model ? (
                    <>
                      <dt>Model</dt>
                      <dd className="mono">{shortModel(attempt.model)}</dd>
                    </>
                  ) : null}
                  {attempt.input_tokens !== null || attempt.output_tokens !== null ? (
                    <>
                      <dt>Tokens</dt>
                      <dd className="mono">
                        {formatNumber(attempt.input_tokens)} in ·{" "}
                        {formatNumber(attempt.output_tokens)} out
                      </dd>
                    </>
                  ) : null}
                  {attempt.tool_calls ? (
                    <>
                      <dt>Tool calls</dt>
                      <dd className="mono">{attempt.tool_calls}</dd>
                    </>
                  ) : null}
                  <dt>Duration</dt>
                  <dd className="mono">{formatDuration(attempt.duration_ms)}</dd>
                  {attempt.error_code ? (
                    <>
                      <dt>Error</dt>
                      <dd style={{ color: "var(--danger)" }}>
                        {attempt.error_code}
                        {attempt.error_message ? ` — ${attempt.error_message}` : ""}
                      </dd>
                    </>
                  ) : null}
                </dl>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {node.error ? (
        <div className="inspector-error">
          <p className="eyebrow" style={{ color: "var(--danger)" }}>
            Recorded failure
          </p>
          <p className="mono">{node.error.code}</p>
          <p style={{ fontSize: "0.8125rem" }}>{node.error.message}</p>
        </div>
      ) : null}
    </div>
  );
}

function FragmentRow({ label, value }: { label: string; value: string | number | null }) {
  const isHash = typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  return (
    <>
      <dt>{label}</dt>
      <dd className={isHash ? "hash" : "mono"}>{value ?? "Not recorded"}</dd>
    </>
  );
}

function LaneInspector({ lane, claims }: { lane: SourceLane; claims: Claim[] }) {
  return (
    <div className="stack">
      <header className="stack-sm" style={{ gap: "0.35rem" }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <p className="eyebrow">{lane.source_tier_label}</p>
          <Pill status={lane.status} />
        </div>
        <h2 style={{ wordBreak: "break-word" }}>{lane.title ?? lane.publisher_domain}</h2>
        <a
          className="mono"
          href={lane.url}
          target="_blank"
          rel="noreferrer noopener"
          style={{ color: "var(--evidence)", wordBreak: "break-all", fontSize: "0.75rem" }}
        >
          {lane.url}
        </a>
      </header>

      <Section title="Acquisition record">
        <dl className="kv">
          <dt>Publisher</dt>
          <dd className="mono">{lane.publisher_domain}</dd>
          <dt>HTTP status</dt>
          <dd className="mono">{lane.http_status ?? "—"}</dd>
          <dt>Media type</dt>
          <dd className="mono">{lane.media_type ?? "—"}</dd>
          <dt>Snapshot size</dt>
          <dd className="mono">{formatBytes(lane.byte_size)}</dd>
          <dt>Snapshot kind</dt>
          <dd className="mono">{lane.snapshot_kind ?? "—"}</dd>
          <dt>Redactions</dt>
          <dd className="mono">{lane.redaction_count}</dd>
          <dt>Retrieved</dt>
          <dd>{formatDateTime(lane.retrieved_at)}</dd>
          <dt>SHA-256</dt>
          <dd className="hash">{lane.raw_sha256 ?? "—"}</dd>
        </dl>
      </Section>

      {lane.error_code ? (
        <div className="inspector-error">
          <p className="eyebrow" style={{ color: "var(--danger)" }}>
            Withheld from evidence
          </p>
          <p className="mono">{lane.error_code}</p>
          <p style={{ fontSize: "0.8125rem" }}>{lane.error_message}</p>
        </div>
      ) : null}

      <Section title={`Claims from this source · ${claims.length}`}>
        {claims.length === 0 ? (
          <p className="muted" style={{ fontSize: "0.8125rem" }}>
            {lane.status === "fetched"
              ? "No claim from this snapshot passed exact-span validation."
              : lane.status === "discovered"
                ? "This candidate has not been captured yet."
                : "Nothing was captured from this source, so it contributes no evidence."}
          </p>
        ) : (
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {claims.map((claim) => (
              <li key={claim.id} className="claim-mini">
                <span className="eyebrow">{claim.category_label}</span>
                <span>{claim.statement}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

function RunInspector({ payload }: { payload: RunPayload }) {
  const { run } = payload;
  const usage = run.usage ?? {};
  const budgets = run.budgets ?? {};
  return (
    <div className="stack">
      <header className="stack-sm" style={{ gap: "0.35rem" }}>
        <p className="eyebrow">Run contract</p>
        <h2>Pinned for this run</h2>
        <p className="muted" style={{ fontSize: "0.8125rem" }}>
          Budgets, model and source policy are frozen when the run is created. Select any stage or
          source lane to inspect it.
        </p>
      </header>

      <Section title="Identity and scope">
        <dl className="kv">
          <dt>Company</dt>
          <dd>{run.company_name}</dd>
          <dt>Number</dt>
          <dd className="mono">{run.company_number ?? "—"}</dd>
          <dt>Cutoff</dt>
          <dd className="mono">{formatDate(run.cutoff)}</dd>
          <dt>Started by</dt>
          <dd>{run.created_by}</dd>
          <dt>Status</dt>
          <dd>{statusLabel(run.status)}</dd>
        </dl>
      </Section>

      <Section title="Versions">
        <dl className="kv">
          <dt>Model</dt>
          <dd className="mono">{run.model}</dd>
          <dt>Prompt</dt>
          <dd className="mono">{run.prompt_version}</dd>
          <dt>Source policy</dt>
          <dd className="mono">{run.source_policy_version}</dd>
          <dt>Fingerprint</dt>
          <dd className="hash">{run.request_fingerprint}</dd>
        </dl>
      </Section>

      <Section title="Budget consumption">
        <ul className="budget-list">
          <BudgetRow
            label="Model calls"
            used={usage.model_calls ?? 0}
            limit={budgets.model_calls ?? 0}
          />
          <BudgetRow
            label="Search tool calls"
            used={usage.tool_calls ?? 0}
            limit={budgets.max_tool_calls ?? 0}
          />
          <BudgetRow
            label="Sources"
            used={payload.lanes.length}
            limit={budgets.max_sources ?? 0}
          />
        </ul>
        <dl className="kv" style={{ marginTop: "0.6rem" }}>
          <dt>Input tokens</dt>
          <dd className="mono">{formatNumber(usage.input_tokens ?? 0)}</dd>
          <dt>Output tokens</dt>
          <dd className="mono">{formatNumber(usage.output_tokens ?? 0)}</dd>
          <dt>Execution budget</dt>
          <dd className="mono">
            {budgets.max_elapsed_seconds
              ? formatDuration(budgets.max_elapsed_seconds * 1000)
              : "Legacy run"}
          </dd>
        </dl>
      </Section>

      {payload.limitations.length > 0 ? (
        <Section title="Stated limitations">
          <ul className="stack-sm" style={{ paddingLeft: "1rem", margin: 0, fontSize: "0.8125rem" }}>
            {payload.limitations.map((line) => (
              <li key={line} className="muted">
                {line}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {run.error_code ? (
        <div className="inspector-error">
          <p className="eyebrow" style={{ color: "var(--danger)" }}>
            Run error
          </p>
          <p className="mono">{humanize(run.error_code)}</p>
          <p style={{ fontSize: "0.8125rem" }}>{run.error_message}</p>
        </div>
      ) : null}
    </div>
  );
}

function BudgetRow({ label, used, limit }: { label: string; used: number; limit: number }) {
  const ratio = limit > 0 ? Math.min(1, used / limit) : 0;
  return (
    <li>
      <div className="row" style={{ justifyContent: "space-between", fontSize: "0.75rem" }}>
        <span className="muted">{label}</span>
        <span className="mono">
          {used} / {limit || "—"}
        </span>
      </div>
      <div className="budget-track" aria-hidden="true">
        <div
          className="budget-fill"
          data-full={ratio >= 1}
          style={{ width: `${Math.round(ratio * 100)}%` }}
        />
      </div>
    </li>
  );
}
