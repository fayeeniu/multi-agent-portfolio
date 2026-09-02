"use client";

import { useResource } from "@/lib/hooks";
import type { SessionPayload } from "@/lib/types";

const MODE_LABEL: Record<string, string> = {
  live: "Public research open",
  fixture: "Fixture research · synthetic",
  closed: "Research gates closed",
};

export function BoundaryTag() {
  const { data } = useResource<SessionPayload>("session");
  const mode = data?.system.research_mode ?? "closed";
  const reviewer = data?.system.reviewer ?? null;
  return (
    <p className="boundary-tag" title={data?.system.boundary ?? "Contacting the research service"}>
      <span className="boundary-dot" data-mode={mode} aria-hidden="true" />
      {data
        ? `${MODE_LABEL[mode] ?? mode} · ${reviewer ?? "no reviewer set"}`
        : "Contacting research service"}
    </p>
  );
}
