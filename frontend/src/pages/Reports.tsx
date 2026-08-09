import { Clock3, Users, TrendingUp, Database, Download, RefreshCw } from "lucide-react";
import StatCard from "../components/StatCard";
import { useReportsData, REPORT_RANGES, type ReportRange } from "../hooks/useReportsData";
import { useState } from "react";
import "./Reports.css";

export default function Reports() {
  const [range, setRange] = useState<ReportRange>("7d");
  const { summary, evaluationMetrics, exports, isLoading, error, downloadUrl, refresh } =
    useReportsData(range);

  return (
    <div className="reports-page">
      <div className="reports-toolbar">
        <div className="reports-range-toggle">
          {REPORT_RANGES.map((r) => (
            <button
              key={r.value}
              className={`reports-range-btn${r.value === range ? " reports-range-btn-active" : ""}`}
              onClick={() => setRange(r.value)}
              aria-pressed={r.value === range}
            >
              {r.label}
            </button>
          ))}
        </div>
        <button className="reports-refresh-btn" onClick={refresh} disabled={isLoading}>
          <RefreshCw size={13} strokeWidth={2.25} className={isLoading ? "reports-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="reports-error-banner">
          Couldn't load report data: {error}
        </div>
      )}

      <div className="reports-stat-grid">
        <StatCard
          icon={<Clock3 size={16} strokeWidth={2} />}
          label="Hours tracked"
          value={summary ? summary.totalHoursTracked.toFixed(1) : "—"}
          unit="hrs"
          sub={summary?.rangeLabel ?? "—"}
          tone="blue"
          tag={isLoading ? "Loading" : "Live"}
        />
        <StatCard
          icon={<Users size={16} strokeWidth={2} />}
          label="Avg occupancy"
          value={summary ? summary.avgOccupancy.toFixed(1) : "—"}
          sub={summary?.rangeLabel ?? "—"}
          tone="signal"
          tag={isLoading ? "Loading" : "Live"}
        />
        <StatCard
          icon={<TrendingUp size={16} strokeWidth={2} />}
          label="Peak occupancy"
          value={summary ? String(summary.peakOccupancy) : "—"}
          sub={summary?.peakAt ?? "—"}
          tone="amber"
          tag={isLoading ? "Loading" : "Live"}
        />
        <StatCard
          icon={<Database size={16} strokeWidth={2} />}
          label="Data completeness"
          value={summary ? String(summary.dataCompletenessPercent) : "—"}
          unit="%"
          sub={summary?.rangeLabel ?? "—"}
          tone="neutral"
          tag={isLoading ? "Loading" : "Live"}
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

        {evaluationMetrics.length === 0 ? (
          <div className="reports-empty-state">
            {isLoading
              ? "Loading evaluation metrics…"
              : "No ground-truth samples in this range yet — evaluation metrics need logged occupancy_ground_truth data to compare against."}
          </div>
        ) : (
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
        )}
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

        {exports.length === 0 ? (
          <div className="reports-empty-state">
            {isLoading ? "Loading exports…" : "No exports available for this range."}
          </div>
        ) : (
          exports.map((r) => (
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
                <a className="reports-download-btn" href={downloadUrl(r.id)}>
                  <Download size={13} strokeWidth={2.25} />
                  Download
                </a>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
