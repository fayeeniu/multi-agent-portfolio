import type { GraphNode } from "./types";

const EXECUTING_DETAIL = "Executing now. The stage holds an exclusive claim.";

export interface InflightStage {
  capability: string;
  since: number;
}

/** Next persisted task the orchestrator will claim. */
export function nextTaskCapability(nodes: readonly GraphNode[]): string {
  return (
    nodes.find(
      (node) => node.kind === "task" && (node.status === "pending" || node.status === "failed"),
    )?.id ?? ""
  );
}

/**
 * Optimistic "running" is only for the stage this browser is advancing.
 * A succeeded planner must keep its persisted duration when a later stage
 * is in flight — otherwise a stale capability paints Planning as executing
 * and both cards share the later stage's reset clock.
 */
export function applyInflightOverlay(
  nodes: readonly GraphNode[],
  inflight: InflightStage | null,
): GraphNode[] {
  if (!inflight?.capability) return [...nodes];
  return nodes.map((node) => {
    if (node.id !== inflight.capability) return node;
    if (node.status !== "pending" && node.status !== "failed") return node;
    return { ...node, status: "running", detail: EXECUTING_DETAIL };
  });
}
