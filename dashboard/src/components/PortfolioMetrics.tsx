import { Pill } from "@/components/ui";
import { humanize } from "@/lib/format";
import type { InvestmentMetric, InvestmentReportProposal } from "@/lib/types";

function metricTone(status: InvestmentMetric["status"]): string {
  if (status === "public_evidence") return "evidence";
  if (status === "document_required") return "human";
  return "danger";
}

function metricValue(metric: InvestmentMetric): string | null {
  const evidence = metric.evidence.find((item) => item.reported_value);
  if (!evidence?.reported_value) return null;
  return evidence.currency
    ? `${evidence.currency} ${evidence.reported_value}`
    : evidence.reported_value;
}

export function PortfolioMetrics({ report }: { report: InvestmentReportProposal }) {
  return (
    <div className="metric-workbench">
      <div className="metric-summary" aria-label="CBIT metric completion summary">
        <div><strong>{report.summary.defined_metrics}</strong><span>defined inputs</span></div>
        <div data-tone="evidence"><strong>{report.summary.publicly_evidenced}</strong><span>publicly evidenced</span></div>
        <div data-tone="human"><strong>{report.summary.document_required}</strong><span>document required</span></div>
        <div data-tone="danger"><strong>{report.summary.not_found_publicly}</strong><span>not found publicly</span></div>
        <div><strong>{report.summary.definition_required}</strong><span>questions to split</span></div>
      </div>

      <div className="metric-categories">
        {report.categories.map((category) => {
          const populated = category.metrics.filter((metric) => metric.status === "public_evidence").length;
          return (
            <details className="metric-category" key={category.key} open={populated > 0}>
              <summary>
                <span>
                  <strong>{category.key}</strong>
                  <small>{category.metrics.length} metrics · {populated} publicly evidenced</small>
                </span>
                <span className="mono">{populated}/{category.metrics.length}</span>
              </summary>
              <div className="metric-table-wrap">
                <table className="metric-table">
                  <thead>
                    <tr><th>Metric</th><th>Status</th><th>Reported value</th><th>Period</th><th>Evidence</th></tr>
                  </thead>
                  <tbody>
                    {category.metrics.map((metric) => {
                      const value = metricValue(metric);
                      const firstEvidence = metric.evidence[0];
                      return (
                        <tr key={metric.key}>
                          <td>
                            <strong>{metric.label}</strong>
                            <small className="mono">{metric.key}</small>
                          </td>
                          <td><Pill tone={metricTone(metric.status)} label={humanize(metric.status)} /></td>
                          <td className="mono">{value ?? "—"}</td>
                          <td>{humanize(metric.period_semantics)}</td>
                          <td>
                            {firstEvidence ? (
                              <a href={firstEvidence.source_url} target="_blank" rel="noreferrer noopener">
                                {metric.evidence.length} exact span{metric.evidence.length === 1 ? "" : "s"}
                              </a>
                            ) : metric.status === "document_required" ? (
                              <span className="muted">Company document or structured submission</span>
                            ) : (
                              <span className="muted">No admitted public span</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </details>
          );
        })}
      </div>

      <div className="metric-holds">
        <div>
          <p className="eyebrow">Definition controls</p>
          <h3>Compound workbook questions remain held</h3>
          <p className="muted">
            A value is not comparable until amount, percentage, period and denominator are separated.
          </p>
        </div>
        <ul>
          {report.held_questions.map((question) => (
            <li key={question.row}>
              <strong>{question.label}</strong>
              <span>{question.required_fields.map(humanize).join(" · ")}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="report-proposal">
        <div>
          <p className="eyebrow">Investment report proposal</p>
          <h3>Evidence-led IC report structure</h3>
          <p className="muted">{report.decision_boundary}</p>
        </div>
        <ol>
          {report.report_sections.map((section, index) => (
            <li key={section.key}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div><strong>{section.heading}</strong><small>{section.purpose}</small></div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
