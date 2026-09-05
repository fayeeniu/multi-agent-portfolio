"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { GraphNode, NodeStatus, SourceLane } from "@/lib/types";
import { formatDuration, shortModel, statusLabel } from "@/lib/format";
import { useElapsed, usePrefersReducedMotion } from "@/lib/hooks";

const CAPTURE_ID = "capture_sources";
const EXTRACT_ID = "extract_claims";

interface Point {
  x: number;
  y: number;
}

interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
  cx: number;
  cy: number;
}

type Selection =
  | { kind: "node"; id: string }
  | { kind: "lane"; id: string }
  | null;

export interface AgentGraphProps {
  nodes: GraphNode[];
  lanes: SourceLane[];
  selection: Selection;
  onSelect: (selection: Selection) => void;
  /** Wall-clock start of the stage currently executing in this browser, if any. */
  runningSince: number | null;
  /** Task id that owns `runningSince`. Other nodes keep their persisted duration. */
  runningCapability: string | null;
}

function measure(element: HTMLElement, origin: DOMRect): Box {
  const rect = element.getBoundingClientRect();
  return {
    left: rect.left - origin.left,
    right: rect.right - origin.left,
    top: rect.top - origin.top,
    bottom: rect.bottom - origin.top,
    cx: rect.left - origin.left + rect.width / 2,
    cy: rect.top - origin.top + rect.height / 2,
  };
}

const ROW_TOL = 28;

function sameRow(from: Box, to: Box): boolean {
  return Math.abs(from.cy - to.cy) < ROW_TOL;
}

function allNodesInOneRow(nodes: GraphNode[], boxes: Map<string, Box>): boolean {
  const measured = nodes
    .map((node) => boxes.get(`node:${node.id}`))
    .filter((box): box is Box => Boolean(box));
  const origin = measured[0];
  if (!origin || measured.length < 2) return true;
  return measured.every((box) => Math.abs(box.cy - origin.cy) < ROW_TOL);
}

type PortDir = "left" | "right" | "top" | "bottom";

function outDir(from: Box, to: Box): PortDir {
  return sameRow(from, to) ? "right" : "bottom";
}

function inDir(from: Box, to: Box): PortDir {
  return sameRow(from, to) ? "left" : "top";
}

function spinePath(from: Box, to: Box): string {
  if (sameRow(from, to)) {
    const start: Point = { x: from.right + 5, y: from.cy };
    const end: Point = { x: to.left - 5, y: to.cy };
    const mid = (start.x + end.x) / 2;
    return `M ${start.x} ${start.y} C ${mid} ${start.y}, ${mid} ${end.y}, ${end.x} ${end.y}`;
  }
  const start: Point = { x: from.cx, y: from.bottom + 5 };
  const end: Point = { x: to.cx, y: to.top - 5 };
  const mid = (start.y + end.y) / 2;
  return `M ${start.x} ${start.y} C ${start.x} ${mid}, ${end.x} ${mid}, ${end.x} ${end.y}`;
}

function spineJoint(from: Box, to: Box): Point {
  if (sameRow(from, to)) {
    return { x: (from.right + to.left) / 2, y: (from.cy + to.cy) / 2 };
  }
  return { x: (from.cx + to.cx) / 2, y: (from.bottom + to.top) / 2 };
}

function laneSpread(index: number, count: number, width: number): number {
  if (count <= 1) return 0;
  return (index / (count - 1) - 0.5) * width;
}

function branchPath(from: Box, to: Box, spread = 0): string {
  const start: Point = { x: from.cx + spread, y: from.bottom + 4 };
  const end: Point = { x: to.cx, y: to.top - 4 };
  const lift = Math.max(40, (end.y - start.y) * 0.55);
  return `M ${start.x} ${start.y} C ${start.x} ${start.y + lift}, ${end.x} ${end.y - lift}, ${end.x} ${end.y}`;
}

function returnPath(from: Box, to: Box, spread = 0): string {
  const start: Point = { x: from.cx, y: from.top - 4 };
  const end: Point = { x: to.cx + spread, y: to.bottom + 4 };
  const lift = Math.max(36, (start.y - end.y) * 0.52);
  return `M ${start.x} ${start.y} C ${start.x} ${start.y - lift}, ${end.x} ${end.y + lift}, ${end.x} ${end.y}`;
}

type EdgeTone = "idle" | "armed" | "flowing" | "done" | "severed";
type EdgeRole = "spine" | "branch" | "return";

function laneTone(lane: SourceLane, captureStatus: NodeStatus | undefined): EdgeTone {
  if (captureStatus === "running" && lane.status === "discovered") return "flowing";
  if (lane.status === "blocked" || lane.status === "failed") return "severed";
  if (lane.status === "fetched") return "done";
  return "idle";
}

function laneCaption(lane: SourceLane): string {
  const label = statusLabel(lane.status);
  return lane.http_status ? `${label} HTTP ${lane.http_status}` : label;
}

interface Drawn {
  id: string;
  d: string;
  tone: EdgeTone;
  role: EdgeRole;
  emphasised: boolean;
}

interface Joint {
  id: string;
  x: number;
  y: number;
  tone: EdgeTone;
}

function edgeStroke(tone: EdgeTone): string {
  if (tone === "severed") return "var(--graph-fail)";
  if (tone === "idle") return "var(--graph-stub-idle)";
  return "var(--graph-ok)";
}

export function AgentGraph({
  nodes,
  lanes,
  selection,
  onSelect,
  runningSince,
  runningCapability,
}: AgentGraphProps) {
  const wrapper = useRef<HTMLDivElement | null>(null);
  const nodeRefs = useRef(new Map<string, HTMLElement>());
  const laneRefs = useRef(new Map<string, HTMLElement>());
  const [boxes, setBoxes] = useState<Map<string, Box>>(new Map());
  const [size, setSize] = useState({ width: 0, height: 0 });
  const reduced = usePrefersReducedMotion();
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");

  const remeasure = useCallback(() => {
    const host = wrapper.current;
    if (!host) return;
    const origin = host.getBoundingClientRect();
    const next = new Map<string, Box>();
    nodeRefs.current.forEach((element, key) => {
      if (element.isConnected) next.set(`node:${key}`, measure(element, origin));
    });
    laneRefs.current.forEach((element, key) => {
      if (element.isConnected) next.set(`lane:${key}`, measure(element, origin));
    });
    setBoxes(next);
    setSize({ width: origin.width, height: origin.height });
  }, []);

  const scheduleMeasure = useCallback(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(remeasure);
    });
  }, [remeasure]);

  useLayoutEffect(() => {
    remeasure();
    const frame = requestAnimationFrame(() => remeasure());
    return () => cancelAnimationFrame(frame);
  }, [remeasure, nodes, lanes]);

  useEffect(() => {
    const host = wrapper.current;
    if (!host) return;
    const observer = new ResizeObserver(() => scheduleMeasure());
    observer.observe(host);
    const spine = host.querySelector(".graph-spine");
    const grid = host.querySelector(".lane-grid");
    if (spine) observer.observe(spine);
    if (grid) observer.observe(grid);
    window.addEventListener("resize", scheduleMeasure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", scheduleMeasure);
    };
  }, [scheduleMeasure]);

  const statusById = new Map<string, NodeStatus>(nodes.map((node) => [node.id, node.status]));
  const cssWrapped = Boolean(
    wrapper.current && getComputedStyle(wrapper.current.querySelector(".graph-spine") ?? wrapper.current).display === "grid",
  );
  const singleRow = allNodesInOneRow(nodes, boxes) && !cssWrapped;
  const layout = singleRow ? "row" : "wrap";

  const [hover, setHover] = useState<Selection>(null);
  const selectedLane = selection?.kind === "lane" ? selection.id : null;
  const selectedNode = selection?.kind === "node" ? selection.id : null;
  const focusLane = hover?.kind === "lane" ? hover.id : selectedLane;
  const focusNode = hover?.kind === "node" ? hover.id : selectedNode;
  const inspecting = focusNode !== null || focusLane !== null;

  const drawn: Drawn[] = [];
  const joints: Joint[] = [];
  const inboundDir = new Map<string, PortDir>();
  const outboundDir = new Map<string, PortDir>();

  // 6-up uses the CSS rule through the card row. Wrapped grids draw the
  // spine from measured boxes so Identity → Human still reads in order.
  if (!singleRow) {
    for (let index = 0; index < nodes.length - 1; index += 1) {
      const from = nodes[index];
      const to = nodes[index + 1];
      if (!from || !to) continue;
      const fromBox = boxes.get(`node:${from.id}`);
      const toBox = boxes.get(`node:${to.id}`);
      if (!fromBox || !toBox) continue;
      let tone: Drawn["tone"] = "idle";
      if (to.status === "running") tone = "flowing";
      else if (to.status === "failed" || to.status === "cancelled") tone = "severed";
      else if (to.status === "succeeded" || to.status === "awaiting") tone = "done";
      else if (from.status === "succeeded") tone = "armed";
      drawn.push({
        id: `spine-${from.id}-${to.id}`,
        d: spinePath(fromBox, toBox),
        tone,
        role: "spine",
        emphasised: focusNode === from.id || focusNode === to.id,
      });
      const joint = spineJoint(fromBox, toBox);
      joints.push({ id: `joint-${from.id}-${to.id}`, x: joint.x, y: joint.y, tone });
      outboundDir.set(from.id, outDir(fromBox, toBox));
      inboundDir.set(to.id, inDir(fromBox, toBox));
    }
  }

  const captureBox = boxes.get(`node:${CAPTURE_ID}`);
  const extractBox = boxes.get(`node:${EXTRACT_ID}`);
  const captureStatus = statusById.get(CAPTURE_ID);
  const fetchedLanes = lanes.filter((lane) => lane.status === "fetched");
  // Real topology only: acquisition fans to every lane; captured lanes return
  // to extraction. No invented links from synthesis or the human gate.
  lanes.forEach((lane, index) => {
    const laneBox = boxes.get(`lane:${lane.id}`);
    if (!laneBox || !captureBox) return;
    drawn.push({
      id: `branch-${lane.id}`,
      d: branchPath(captureBox, laneBox, laneSpread(index, lanes.length, 26)),
      tone: laneTone(lane, captureStatus),
      role: "branch",
      emphasised:
        focusLane === lane.id ||
        focusNode === CAPTURE_ID ||
        (focusNode === EXTRACT_ID && lane.status === "fetched"),
    });
    if (lane.status === "fetched" && extractBox) {
      const fetchedIndex = fetchedLanes.findIndex((item) => item.id === lane.id);
      drawn.push({
        id: `return-${lane.id}`,
        d: returnPath(laneBox, extractBox, laneSpread(fetchedIndex, fetchedLanes.length, 22)),
        tone: statusById.get(EXTRACT_ID) === "running" ? "flowing" : "done",
        role: "return",
        emphasised: focusLane === lane.id || focusNode === EXTRACT_ID,
      });
    }
  });

  const anythingSelected = selection !== null;
  const showCaptureDrop = lanes.length > 0;
  const showExtractDrop = showCaptureDrop && fetchedLanes.length > 0;

  return (
    <div className="graph" data-layout={layout}>
      <div className="graph-scroll">
        <div className="graph-inner" ref={wrapper}>
        <svg
          className="graph-edges"
          viewBox={`0 0 ${Math.max(size.width, 1)} ${Math.max(size.height, 1)}`}
          width={size.width || undefined}
          height={size.height || undefined}
          aria-hidden="true"
          focusable="false"
        >
          <defs>
            {drawn.map((edge) => (
              <path key={`def-${edge.id}`} id={`${uid}-${edge.id}`} d={edge.d} fill="none" />
            ))}
          </defs>
          {drawn.map((edge) => {
            const branchish = edge.role !== "spine";
            const baseOpacity = branchish ? 0.32 : 0.92;
            const opacity =
              inspecting && !edge.emphasised
                ? baseOpacity * 0.22
                : edge.emphasised
                  ? branchish
                    ? 0.78
                    : 1
                  : baseOpacity;
            const showPacket = edge.tone === "flowing" && !reduced && edge.role === "spine";
            return (
              <g key={edge.id}>
                <path
                  d={edge.d}
                  fill="none"
                  stroke={edgeStroke(edge.tone)}
                  strokeWidth={edge.role === "spine" ? 1.45 : 0.85}
                  strokeLinecap="round"
                  strokeDasharray={edge.tone === "idle" ? "3 5" : undefined}
                  opacity={opacity}
                  style={{ transition: "opacity 220ms ease, stroke 220ms ease" }}
                />
                {showPacket ? (
                  <circle r={2.8} fill="var(--graph-ok)" data-packet="true">
                    <animateMotion dur="1.5s" repeatCount="indefinite" rotate="auto">
                      <mpath href={`#${uid}-${edge.id}`} />
                    </animateMotion>
                    <animate
                      attributeName="opacity"
                      values="0;1;1;0"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                ) : null}
              </g>
            );
          })}
          {joints.map((joint) => (
            <circle
              key={joint.id}
              cx={joint.x}
              cy={joint.y}
              r={4}
              fill="var(--graph-plate)"
              stroke={edgeStroke(joint.tone)}
              strokeWidth={1.5}
              opacity={inspecting ? 0.55 : 0.95}
            />
          ))}
        </svg>

        <ol className="graph-spine" aria-label="Bounded agent execution sequence">
          {nodes.map((node, index) => (
            <li
              key={node.id}
              className="graph-cell"
              data-kind={node.kind}
              style={{ listStyle: "none" }}
            >
              <GraphNodeCard
                node={node}
                hasInbound={index > 0}
                hasOutbound={index < nodes.length - 1}
                inboundDir={inboundDir.get(node.id) ?? "left"}
                outboundDir={outboundDir.get(node.id) ?? "right"}
                hasDrop={
                  (node.id === CAPTURE_ID && showCaptureDrop) ||
                  (node.id === EXTRACT_ID && showExtractDrop)
                }
                selected={selectedNode === node.id}
                dimmed={anythingSelected && selectedNode !== node.id && selection?.kind === "node"}
                runningSince={runningSince}
                runningCapability={runningCapability}
                onSelect={() => onSelect(selectedNode === node.id ? null : { kind: "node", id: node.id })}
                onHover={(active) =>
                  setHover(active ? { kind: "node", id: node.id } : null)
                }
                register={(element) => {
                  if (element) nodeRefs.current.set(node.id, element);
                  else nodeRefs.current.delete(node.id);
                }}
              />
            </li>
          ))}
        </ol>

        {lanes.length > 0 ? (
          <section className="graph-lanes" aria-label="Source acquisition lanes">
            <div className="graph-lanes-head">
              <h3 className="graph-lanes-title">
                Source lanes <b>· {lanes.length}</b>
              </h3>
              <p className="graph-lanes-hint">
                One lane per discovered source. Only captured lanes return evidence to extraction.
              </p>
            </div>
            <div className="lane-grid">
              <AnimatePresence initial={false}>
                {lanes.map((lane, index) => (
                  <motion.button
                    key={lane.id}
                    type="button"
                    className="lane"
                    data-status={lane.status}
                    data-tier={lane.source_tier}
                    data-selected={selectedLane === lane.id}
                    data-dimmed={selection?.kind === "lane" && selectedLane !== lane.id}
                    initial={reduced ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduced ? undefined : { opacity: 0, y: -6 }}
                    transition={{ duration: 0.28, delay: reduced ? 0 : Math.min(index * 0.03, 0.3) }}
                    onClick={() =>
                      onSelect(selectedLane === lane.id ? null : { kind: "lane", id: lane.id })
                    }
                    onPointerEnter={() => setHover({ kind: "lane", id: lane.id })}
                    onPointerLeave={() => setHover(null)}
                    ref={(element) => {
                      if (element) laneRefs.current.set(lane.id, element);
                      else laneRefs.current.delete(lane.id);
                    }}
                  >
                    <span className="lane-top">
                      <span className="lane-domain" title={lane.publisher_domain}>
                        {lane.publisher_domain}
                      </span>
                      <span className="lane-tier">
                        {lane.source_tier === "official"
                          ? "official"
                          : lane.source_tier === "first_party"
                            ? "first party"
                            : "public"}
                      </span>
                    </span>
                    <span className="lane-meta">
                      <span className="lane-state">{laneCaption(lane)}</span>
                      {lane.claim_count > 0 ? <span>{lane.claim_count} claims</span> : null}
                    </span>
                  </motion.button>
                ))}
              </AnimatePresence>
            </div>
          </section>
        ) : null}
        </div>
      </div>

      <div className="graph-legend">
        <span>
          <i className="engine-mark" data-engine="model" aria-hidden="true" /> reasoning model
        </span>
        <span>
          <i className="engine-mark" data-engine="model" data-tier="repair" aria-hidden="true" /> repair model
        </span>
        <span>
          <i className="engine-mark" data-engine="deterministic" aria-hidden="true" /> deterministic stage
        </span>
        <span>
          <i className="engine-mark" data-engine="human" aria-hidden="true" /> human gate
        </span>
        <span>
          <i className="engine-mark" data-engine="fail" aria-hidden="true" /> withheld or failed
        </span>
      </div>
    </div>
  );
}

interface CardProps {
  node: GraphNode;
  selected: boolean;
  dimmed: boolean;
  hasInbound: boolean;
  hasOutbound: boolean;
  inboundDir: PortDir;
  outboundDir: PortDir;
  hasDrop: boolean;
  runningSince: number | null;
  runningCapability: string | null;
  onSelect: () => void;
  onHover: (active: boolean) => void;
  register: (element: HTMLElement | null) => void;
}

function GraphNodeCard({
  node,
  selected,
  dimmed,
  hasInbound,
  hasOutbound,
  inboundDir,
  outboundDir,
  hasDrop,
  runningSince,
  runningCapability,
  onSelect,
  onHover,
  register,
}: CardProps) {
  const live =
    node.status === "running" &&
    (runningCapability === null || runningCapability === node.id);
  const elapsed = useElapsed(live, runningSince);
  return (
    <button
      type="button"
      className="gnode"
      data-status={node.status}
      data-selected={selected}
      data-dimmed={dimmed}
      onClick={onSelect}
      onPointerEnter={() => onHover(true)}
      onPointerLeave={() => onHover(false)}
      ref={register}
      aria-pressed={selected}
    >
      {hasInbound ? (
        <span className="gnode-port" data-side="in" data-dir={inboundDir} aria-hidden="true" />
      ) : null}
      {hasOutbound && !(hasDrop && outboundDir === "bottom") ? (
        <span className="gnode-port" data-side="out" data-dir={outboundDir} aria-hidden="true" />
      ) : null}
      {hasDrop ? <span className="gnode-port" data-side="drop" aria-hidden="true" /> : null}
      <span className="gnode-top">
        <span className="gnode-layer" title={node.layer}>
          {node.layer}
        </span>
        <span
          className="gnode-engine"
          data-engine={node.engine}
          data-tier={node.route?.tier ?? undefined}
          title={
            node.route
              ? `Routed to ${node.route.model} at ${node.route.effort} reasoning effort`
              : undefined
          }
        >
          <i
            className="engine-mark"
            data-engine={node.engine}
            data-tier={node.route?.tier ?? undefined}
            aria-hidden="true"
          />
          {node.engine === "model"
            ? shortModel(node.route?.model)
            : node.engine === "human"
              ? "human"
              : "code"}
        </span>
      </span>
      <span className="gnode-label">{node.label}</span>
      <span className="gnode-detail">{node.detail}</span>
      <span className="gnode-foot">
        <span>{statusLabel(node.status)}</span>
        {live && runningSince !== null ? (
          <span className="gnode-timer">{formatDuration(elapsed)}</span>
        ) : node.duration_ms !== null ? (
          <span className="gnode-metric">{formatDuration(node.duration_ms)}</span>
        ) : node.attempts ? (
          <span className="gnode-metric">
            {node.attempts.count}/{node.attempts.max}
          </span>
        ) : null}
      </span>
    </button>
  );
}
