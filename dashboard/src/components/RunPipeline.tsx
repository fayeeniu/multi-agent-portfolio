"use client";

import type { RunSummary } from "@/lib/types";

const STAGES = [
  { key: "discover_sources", short: "Plan" },
  { key: "capture_sources", short: "Capture" },
  { key: "extract_claims", short: "Extract" },
  { key: "compose_deck", short: "Compose" },
];

/** Compact read of one run's persisted stage progress. */
export function RunPipeline({ run }: { run: RunSummary }) {
  const activeIndex = STAGES.findIndex((stage) => stage.key === run.active_capability);
  const done = run.stages_done;
  const terminal =
    run.status === "pending_review" ||
    run.status === "approved" ||
    run.status === "rejected";
  return (
    <div className="pipeline" aria-label={`Stage progress: ${done} of ${STAGES.length} complete`}>
      {STAGES.map((stage, index) => {
        const state =
          index < done
            ? "done"
            : index === activeIndex && run.status === "running"
              ? "live"
              : index === activeIndex
                ? "next"
                : run.status === "failed" && index === done
                  ? "failed"
                  : "idle";
        return (
          <span key={stage.key} className="pipeline-step" data-state={state}>
            <i aria-hidden="true" />
            <em>{stage.short}</em>
          </span>
        );
      })}
      <span className="pipeline-step" data-state={terminal ? (run.status === "pending_review" ? "await" : "done") : "idle"}>
        <i aria-hidden="true" />
        <em>Review</em>
      </span>
    </div>
  );
}
