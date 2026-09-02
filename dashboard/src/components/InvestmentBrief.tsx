import { Pill } from "@/components/ui";
import { formatNumber } from "@/lib/format";
import type { Claim, CompanyPayload } from "@/lib/types";

const DIMENSIONS = [
  {
    key: "identity",
    label: "Company & governance",
    detail: "Legal status, filings and material corporate actions.",
    categories: ["identity", "corporate_actions"],
  },
  {
    key: "market",
    label: "Market & commercial",
    detail: "Products, customers, partnerships and independent market context.",
    categories: ["products_market", "public_discourse"],
  },
  {
    key: "finance",
    label: "Finance & scale",
    detail: "Capital, grants and reported operating or financial performance.",
    categories: ["funding", "awards", "performance"],
  },
  {
    key: "risk",
    label: "Risk & regulation",
    detail: "Disclosed constraints, adverse evidence and regulatory exposure.",
    categories: ["challenges", "regulation"],
  },
  {
    key: "technology",
    label: "Technology evidence",
    detail: "Public product, engineering, repository and technical footprint evidence.",
    categories: ["technology"],
  },
] as const;

function dimensionStatus(count: number, categoryCount: number): { label: string; tone: string } {
  if (count === 0) return { label: "Evidence gap", tone: "danger" };
  if (count < categoryCount) return { label: "Limited", tone: "human" };
  return { label: "Covered", tone: "evidence" };
}

/**
 * A decision-neutral diligence model. It measures admitted evidence coverage;
 * it does not infer attractiveness, value the company or issue a recommendation.
 */
export function InvestmentBrief({ data }: { data: CompanyPayload }) {
  const claims = data.sections.flatMap((section) => section.claims);
  const dimensions = DIMENSIONS.map((dimension) => {
    const matches = claims.filter((claim) =>
      (dimension.categories as readonly string[]).includes(claim.category),
    );
    const categoriesCovered = new Set(matches.map((claim) => claim.category)).size;
    const sourceCount = new Set(matches.map((claim) => claim.source_id)).size;
    return {
      ...dimension,
      claims: matches,
      categoriesCovered,
      sourceCount,
      status: dimensionStatus(categoriesCovered, dimension.categories.length),
    };
  });
  const independent = claims.filter((claim) => claim.perspective === "fact").length;
  const firstParty = claims.filter((claim) => claim.perspective === "company_self_claim").length;
  const contradictions = Number(data.profile?.content.coverage &&
    typeof data.profile.content.coverage === "object" &&
    "contradiction_candidates" in data.profile.content.coverage
      ? data.profile.content.coverage.contradiction_candidates
      : 0);
  const metricSummary = data.investment_report?.summary ?? null;
  const publicMetricTarget = metricSummary
    ? metricSummary.defined_metrics - metricSummary.document_required
    : 0;
  const coverage = metricSummary && publicMetricTarget
    ? Math.round((metricSummary.publicly_evidenced / publicMetricTarget) * 100)
    : null;

  return (
    <div className="investment-brief">
      <div className="assessment-head">
        <div>
          <p className="eyebrow">Decision-neutral diligence model</p>
          <h2>Investment evidence brief</h2>
          <p className="muted">
            Coverage reflects admitted, source-linked evidence only. It is not an investment
            score, valuation, forecast or recommendation.
          </p>
        </div>
        <div
          className="coverage-ring"
          data-tone="evidence"
          style={{ "--coverage": `${coverage ?? 0}%` } as React.CSSProperties}
        >
          <strong>{coverage === null ? "—" : `${coverage}%`}</strong>
          <span>{coverage === null ? "metrics pending" : "public metrics"}</span>
        </div>
      </div>

      <div className="assessment-grid">
        {dimensions.map((dimension) => (
          <article className="assessment-card" key={dimension.key}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h3>{dimension.label}</h3>
              <Pill tone={dimension.status.tone} label={dimension.status.label} />
            </div>
            <p>{dimension.detail}</p>
            <div className="assessment-meta">
              <span><b>{formatNumber(dimension.claims.length)}</b> claims</span>
              <span><b>{formatNumber(dimension.sourceCount)}</b> sources</span>
            </div>
          </article>
        ))}
      </div>

      <div className="evidence-balance" aria-label="Evidence composition">
        <span>Independent or official <b>{independent}</b></span>
        <span>First-party <b>{firstParty}</b></span>
        <span>Contradictions <b>{Number.isFinite(contradictions) ? contradictions : 0}</b></span>
        <span>Captured sources <b>{data.lanes.filter((lane) => lane.status === "fetched").length}</b></span>
        {metricSummary ? (
          <>
            <span>CBIT metrics evidenced <b>{metricSummary.publicly_evidenced}/{metricSummary.defined_metrics}</b></span>
            <span>Document-required metrics <b>{metricSummary.document_required}</b></span>
          </>
        ) : (
          <span>CBIT metric report <b>not generated</b></span>
        )}
      </div>
    </div>
  );
}

export function claimsForCategories(
  data: CompanyPayload,
  categories: readonly string[],
): Claim[] {
  return data.sections
    .filter((section) => categories.includes(section.key))
    .flatMap((section) => section.claims);
}
