"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import { Pill } from "@/components/ui";
import { usePrefersReducedMotion } from "@/lib/hooks";
import type { Claim, SourceLane } from "@/lib/types";

/**
 * Claim-to-evidence ledger. Each claim shows the verbatim span that admitted it
 * and the exact source locator it came from; nothing is paraphrased here.
 */
export function ClaimLedger({
  claims,
  lanes,
  highlightSourceId,
}: {
  claims: Claim[];
  lanes: SourceLane[];
  highlightSourceId?: string | null;
}) {
  const reduced = usePrefersReducedMotion();
  const [active, setActive] = useState<string>("all");

  const categories = useMemo(() => {
    const counts = new Map<string, { label: string; count: number }>();
    for (const claim of claims) {
      const current = counts.get(claim.category);
      counts.set(claim.category, {
        label: claim.category_label,
        count: (current?.count ?? 0) + 1,
      });
    }
    return [...counts.entries()].sort((a, b) => b[1].count - a[1].count);
  }, [claims]);

  const laneById = useMemo(
    () => new Map(lanes.map((lane) => [lane.id, lane] as const)),
    [lanes],
  );

  const visible = claims.filter((claim) => {
    if (highlightSourceId) return claim.source_id === highlightSourceId;
    return active === "all" || claim.category === active;
  });

  if (claims.length === 0) {
    return (
      <div className="empty">
        No claim has been admitted yet. Claims appear only after extraction validates each statement
        as a verbatim span of a captured snapshot.
      </div>
    );
  }

  return (
    <div>
      {!highlightSourceId ? (
        <div className="section-tabs" role="group" aria-label="Filter claims by category">
          <button
            type="button"
            className="section-tab"
            aria-pressed={active === "all"}
            onClick={() => setActive("all")}
          >
            All evidence<span>{claims.length}</span>
          </button>
          {categories.map(([key, meta]) => (
            <button
              key={key}
              type="button"
              className="section-tab"
              aria-pressed={active === key}
              onClick={() => setActive(key)}
            >
              {meta.label}
              <span>{meta.count}</span>
            </button>
          ))}
        </div>
      ) : null}

      <AnimatePresence initial={false} mode="popLayout">
        {visible.map((claim, index) => {
          const lane = laneById.get(claim.source_id);
          return (
            <motion.article
              key={claim.id}
              className="claim"
              layout={!reduced}
              initial={reduced ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0 }}
              transition={{ duration: 0.22, delay: reduced ? 0 : Math.min(index * 0.015, 0.2) }}
            >
              <div className="claim-head">
                <span className="eyebrow">{claim.category_label}</span>
                <Pill
                  tone={claim.perspective === "fact" ? "evidence" : "idle"}
                  label={claim.perspective_label}
                />
                {claim.event_date ? (
                  <span className="mono muted" style={{ fontSize: "0.6875rem" }}>
                    {claim.event_date}
                  </span>
                ) : null}
                {claim.amount ? (
                  <span className="mono" style={{ fontSize: "0.6875rem", color: "var(--evidence)" }}>
                    {claim.currency ? `${claim.currency} ` : ""}
                    {claim.amount}
                  </span>
                ) : null}
              </div>
              <p className="claim-statement">{claim.statement}</p>
              <p className="claim-span">{claim.evidence_span}</p>
              <div className="claim-foot">
                <span>{lane?.source_tier_label ?? "Public source"}</span>
                <a href={claim.source_locator} target="_blank" rel="noreferrer noopener">
                  {claim.source_locator}
                </a>
                <span>{claim.extraction_method}</span>
              </div>
            </motion.article>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
