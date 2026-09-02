/** View models projected by the FastAPI control-room API (`portfolio_agent.api`). */

export type Tone = "evidence" | "human" | "danger" | "model" | "idle" | "active";

export interface AgentRole {
  key: string;
  label: string;
  layer: string;
  engine: "model" | "deterministic" | "human";
  summary: string;
  owns: string;
  must_not: string;
  inputs: string;
  outputs: string;
}

export interface SystemState {
  reviewer: string | null;
  reviewer_configured: boolean;
  live_research_enabled: boolean;
  research_mode: "live" | "fixture" | "closed";
  external_model_enabled: boolean;
  live_retrieval_enabled: boolean;
  model: string;
  escalation_model: string;
  runtime: string;
  boundary: string;
  /**
   * Optional for compatibility with a local research service that is still
   * restarting on an older additive API version. The control room must remain
   * readable while the two loopback processes converge.
   */
  model_route?: {
    reasoning?: { model: string; effort: string; stages: string[] };
    selection?: { model: string; effort: string; stages: string[] };
    repair?: { model: string; effort: string; when: string };
  };
  budgets: Record<string, number>;
  agents: AgentRole[];
}

export interface NextAction {
  label: string;
  detail: string;
  href: string | null;
}

export interface CompanyRow {
  id: string;
  name: string;
  entity_type: string;
  jurisdiction: string | null;
  lifecycle_status: string;
  resolution_status: string;
  classification: string;
  created_at: string | null;
  identifier: { id: string; scheme: string; value: string; state: string } | null;
  verified_domain: string | null;
  open_decisions: number;
  case_id: string | null;
  case_count: number;
  artifact_count: number;
  claim_count: number;
  run_count: number;
  latest_run: { id: string; status: string; cutoff: string | null; created_at: string | null } | null;
  next_action: NextAction;
}

export interface SourceCounts {
  total: number;
  discovered?: number;
  fetched?: number;
  blocked?: number;
  unsupported?: number;
  failed?: number;
}

export interface RunSummary {
  id: string;
  company_id: string;
  company_name: string;
  status: string;
  cutoff: string | null;
  created_at: string | null;
  updated_at: string | null;
  model: string;
  source_policy_version: string;
  stages_total: number;
  stages_done: number;
  active_capability: string | null;
  active_role: string | null;
  claim_count: number;
  sources: SourceCounts;
  error_code: string | null;
  profile: {
    id: string;
    version: number;
    status: string;
    content_sha256: string;
  } | null;
}

export interface OverviewPayload {
  system: SystemState;
  next_action: NextAction;
  metrics: Record<string, number>;
  attention: AttentionItem[];
  runs: RunSummary[];
  companies: CompanyRow[];
  live_research_enabled: boolean;
}

export interface AttentionItem {
  id: string;
  kind: string;
  severity: "danger" | "hold" | "review" | "active" | "warning";
  title: string;
  detail: string;
  action_label: string;
  href: string;
}

export interface OutputSummary {
  label: string;
  value: string | number | null;
}

export interface AttemptRow {
  attempt: number;
  status: string;
  model: string | null;
  input_hash: string;
  output_hash: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  tool_calls: number | null;
  duration_ms: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string | null;
}

export type NodeStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "awaiting";

export interface GraphNode {
  id: string;
  kind: "gate" | "task";
  label: string;
  layer: string;
  engine: "model" | "deterministic" | "human";
  status: NodeStatus;
  detail: string;
  summary: string;
  contract: { owns: string; must_not: string; inputs: string; outputs: string };
  attempts: { count: number; max: number } | null;
  route: { tier: "reasoning" | "repair" | "small"; model: string; effort: string } | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  input_hash: string | null;
  output_hash: string | null;
  outputs_summary: OutputSummary[];
  attempt_log: AttemptRow[];
  error: { code: string | null; message: string | null } | null;
  lane_count: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  kind: string;
}

export interface SourceLane {
  id: string;
  url: string;
  requested_url: string;
  title: string | null;
  publisher_domain: string;
  source_tier: string;
  source_tier_label: string;
  status: "discovered" | "fetched" | "blocked" | "unsupported" | "failed";
  http_status: number | null;
  media_type: string | null;
  byte_size: number | null;
  raw_sha256: string | null;
  snapshot_kind: string | null;
  redaction_count: number;
  retrieved_at: string | null;
  error_code: string | null;
  error_message: string | null;
  claim_count: number;
}

export interface Claim {
  id: string;
  source_id: string;
  category: string;
  category_label: string;
  subject_key: string;
  statement: string;
  evidence_span: string;
  source_locator: string;
  event_date: string | null;
  amount: string | null;
  currency: string | null;
  perspective: string;
  perspective_label: string;
  verification_status: string;
  extraction_method: string;
  model: string;
}

export interface ProfileVersion {
  id: string;
  version: number;
  status: string;
  content_sha256: string;
  created_by: string;
  reviewed_by: string | null;
  review_reason: string | null;
  lock_version: number;
  created_at: string | null;
  content: Record<string, unknown>;
}

export interface Contradiction {
  category: string;
  subject_key: string;
  status: string;
  claims: { statement: string; source_url: string }[];
}

export interface RunPayload {
  run: {
    id: string;
    company_id: string;
    company_name: string;
    company_number: string | null;
    research_case_id: string;
    status: string;
    cutoff: string | null;
    created_at: string | null;
    updated_at: string | null;
    created_by: string;
    model: string;
    prompt_version: string;
    source_policy_version: string;
    request_fingerprint: string;
    budgets: Record<string, number>;
    usage: Record<string, number>;
    coverage: Record<string, unknown>;
    cancelled_by: string | null;
    cancellation_reason: string | null;
    error_code: string | null;
    error_message: string | null;
  };
  nodes: GraphNode[];
  edges: GraphEdge[];
  lanes: SourceLane[];
  claims: Claim[];
  profile: ProfileVersion | null;
  contradictions: Contradiction[];
  limitations: string[];
  next_action: NextAction;
  advance?: {
    ok: boolean;
    capability: string | null;
    code: string | null;
    message: string | null;
    elapsed_ms: number;
    retryable: boolean;
    attempts_remaining: number;
  };
}

export interface CompanySection {
  key: string;
  label: string;
  claims: Claim[];
  count: number;
}

export interface InvestmentMetricEvidence {
  claim_id: string;
  statement: string;
  evidence_span: string;
  source_url: string;
  event_date: string | null;
  reported_value: string | null;
  currency: string | null;
  perspective: string;
  verification_status: string;
}

export interface InvestmentMetric {
  key: string;
  label: string;
  data_type: string;
  unit: string | null;
  period_semantics: string;
  sourceability: string;
  status: "public_evidence" | "document_required" | "not_found_publicly";
  evidence: InvestmentMetricEvidence[];
}

export interface InvestmentReportProposal {
  schema_version: string;
  metric_contract_version: string;
  summary: {
    defined_metrics: number;
    publicly_evidenced: number;
    document_required: number;
    not_found_publicly: number;
    definition_required: number;
    derived_metrics: number;
    unmapped_claims: number;
  };
  categories: { key: string; metrics: InvestmentMetric[] }[];
  held_questions: {
    row: number;
    label: string;
    category: string;
    status: "definition_required";
    required_fields: string[];
    reason: string | null;
  }[];
  derived_metrics: {
    key: string;
    label: string;
    status: "inputs_required";
    formula: string;
    required_metrics: string[];
  }[];
  report_sections: {
    key: string;
    heading: string;
    purpose: string;
    categories: string[];
  }[];
  decision_boundary: string;
}

export interface CompanyPayload {
  company: {
    id: string;
    name: string;
    entity_type: string;
    jurisdiction: string | null;
    lifecycle_status: string;
    resolution_status: string;
    classification: string;
    created_at: string | null;
  };
  identifiers: {
    id: string;
    scheme: string;
    scheme_label: string;
    value: string;
    submitted_value: string;
    reviewed: boolean;
    state: string;
    created_at: string | null;
  }[];
  domains: { id: string; url: string; domain: string; status: string; created_at: string | null }[];
  cases: {
    id: string;
    purpose: string;
    classification: string;
    status: string;
    created_at: string | null;
    created_by: string;
  }[];
  artifacts: {
    id: string;
    kind: string;
    kind_label: string;
    normalized_value: string | null;
    original_filename: string | null;
    classification: string;
    content_sha256: string | null;
    actor: string;
    created_at: string | null;
  }[];
  runs: RunSummary[];
  sections: CompanySection[];
  /** Absent on profiles served by a process started before the metric contract existed. */
  investment_report?: InvestmentReportProposal | null;
  lanes: SourceLane[];
  profile: ProfileVersion | null;
  profile_versions: {
    id: string;
    version: number;
    status: string;
    created_at: string | null;
    reviewed_by: string | null;
    content_sha256: string;
    research_run_id: string | null;
  }[];
  next_action: NextAction;
  live_research_enabled: boolean;
}

export interface CompaniesPayload {
  companies: CompanyRow[];
  counts: { total: number; resolved: number; identity_holds: number; with_runs: number };
}

export interface SessionPayload {
  csrf_token: string;
  system: SystemState;
}
