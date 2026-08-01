import { Clock3, Users, TrendingUp, Database, Download } from "lucide-react";
import StatCard from "../components/StatCard";
import { reportSummary, evaluationMetrics, reportExports } from "../data";
import "./Reports.css";

/**
 * Reports page — MOCK DATA, pending backend historical-query support.
 *
 * There is currently no /api/reports/* endpoint; evaluationMetrics,
 * reportSummary, and reportExports are hand-authored fixtures in data.ts
 * shaped to match the contract we've proposed to backend (see the request
 * doc). Once /api/reports/* exists, swap the imports below for a fetch
 * inside a useReportsData hook (mirroring useOccupancyData) — the JSX
 * doesn't need to change since field names already match the proposed
 * response shape.
 */
export default function Reports() {
  return (
    <div className="reports-page">
      <div className="reports-mock-banner">
        Showing sample data — historical backend queries aren't live yet. See the API contract shared with backend for the expected shape.
      </div>

      <div className="reports-stat-grid">
        <StatCard
          icon={<Clock3 size={16} strokeWidth={2} />}
          label="Hours tracked"
          value={reportSummary.totalHoursTracked.toFixed(1)}
          unit="hrs"
          sub={reportSummary.rangeLabel}
          tone="blue"
          tag="Mock"
        />
        <StatCard
          icon={<Users size={16} strokeWidth={2} />}
          label="Avg occupancy"
          value={reportSummary.avgOccupancy.toFixed(1)}
          sub={reportSummary.rangeLabel}
          tone="signal"
          tag="Mock"
        />
        <StatCard
          icon={<TrendingUp size={16} strokeWidth={2} />}
          label="Peak occupancy"
          value={String(reportSummary.peakOccupancy)}
          sub={reportSummary.peakAt}
          tone="amber"
          tag="Mock"
        />
        <StatCard
          icon={<Database size={16} strokeWidth={2} />}
          label="Data completeness"
          value={String(reportSummary.dataCompletenessPercent)}
          unit="%"
          sub={reportSummary.rangeLabel}
          tone="neutral"
          tag="Mock"
        />
      </div>

      <div className="reports-section">
        <div className="reports-section-head">
          <div>
            <div className="reports-section-title">Fusion evaluation metrics</div>
            <div className="reports-section-sub">
              Occupancy count error vs. ground truth, by sensing model
            </div>
          </div>
        </div>

        <table className="reports-table">
          <thead>
            <tr>
              <th>Model</th>
              <th className="num">MAE</th>
              <th className="num">RMSE</th>
              <th className="num">Fusion gain</th>
              <th className="num">Samples</th>
            </tr>
          </thead>
          <tbody>
            {evaluationMetrics.map((m) => (
              <tr key={m.model}>
                <td>{m.model}</td>
                <td className="num">{m.mae.toFixed(2)}</td>
                <td className="num">{m.rmse.toFixed(2)}</td>
                <td className="num">
                  {m.fusionGainPercent === null ? (
                    <span className="reports-gain-baseline">baseline</span>
                  ) : (
                    <span className="reports-gain-positive">
                      &minus;{m.fusionGainPercent.toFixed(1)}% MAE
                    </span>
                  )}
                </td>
                <td className="num">{m.sampleCount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="reports-section">
        <div className="reports-section-head">
          <div>
            <div className="reports-section-title">Historical exports</div>
            <div className="reports-section-sub">
              Downloadable occupancy and evaluation summaries
            </div>
          </div>
        </div>

        {reportExports.map((r) => (
          <div className="reports-export-row" key={r.id}>
            <div>
              <div className="reports-export-name">{r.name}</div>
              <div className="reports-export-meta">
                {r.room} &middot; {r.rangeLabel} &middot; generated{" "}
                {new Date(r.generatedAt).toLocaleDateString()} &middot; {r.sizeKb} KB
              </div>
            </div>
            <div className="reports-export-actions">
              <span className="reports-format-badge">{r.format.toUpperCase()}</span>
              <button className="reports-download-btn" disabled title="Wired up once backend export endpoint exists">
                <Download size={13} strokeWidth={2.25} />
                Download
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
