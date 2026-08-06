import type { LiveMlPrediction } from "../hooks/useMlPrediction";
import "./PredictiveOccupancy.css";

type Props = {
  prediction: LiveMlPrediction | null;
  loading: boolean;
  error: string | null;
};

function percent(value: number | undefined): string {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function forecastLabel(value: string): string {
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PredictiveOccupancy({ prediction, loading, error }: Props) {
  if (loading) {
    return <section className="ml-forecast ml-forecast-empty">Loading predictive occupancy...</section>;
  }
  if (!prediction) {
    return (
      <section className="ml-forecast ml-forecast-empty">
        <strong>Predictive occupancy</strong>
        <span>{error ?? "Waiting for the first completed five-minute sensor window."}</span>
      </section>
    );
  }

  const result = prediction.prediction;
  const recommendation = prediction.recommendation;
  const actions = recommendation.recommended_actions ?? [];
  const warnings = recommendation.warnings ?? [];

  return (
    <section className="ml-forecast">
      <header className="ml-forecast-header">
        <div>
          <p className="ml-eyebrow">30-minute forecast</p>
          <h2>Predictive occupancy</h2>
          <p>
            Five-minute window ending {forecastLabel(prediction.window_end)} · forecast for {forecastLabel(prediction.forecast_time)}
          </p>
        </div>
        <span className="ml-live-badge">AUTO · 5 MIN</span>
      </header>

      <div className="ml-metric-grid">
        <article className="ml-primary-metric">
          <span>Expected occupancy</span>
          <strong>{result.predicted_occupancy}</strong>
          <small>
            Range {result.prediction_interval.lower}–{result.prediction_interval.upper} · confidence {percent(result.confidence)}
          </small>
        </article>
        <article>
          <span>Overcrowding risk</span>
          <strong className={result.overcrowding.overcrowding_risk ? "ml-danger" : "ml-safe"}>
            {result.overcrowding.overcrowding_risk ? "HIGH" : "LOW"}
          </strong>
          <small>{percent(result.overcrowding.risk_probability)} probability</small>
        </article>
        <article>
          <span>Ventilation</span>
          <strong>{result.predicted_ventilation}</strong>
          <small>Recommended level</small>
        </article>
        <article>
          <span>Empty-room probability</span>
          <strong>{percent(result.empty_room.empty_probability_30m)}</strong>
          <small>30 min · {percent(result.empty_room.empty_probability)} at 60 min</small>
        </article>
        <article>
          <span>BLE activity</span>
          <strong>{result.ble_activity_side}</strong>
          <small>Relative signal side</small>
        </article>
      </div>

      <footer className="ml-forecast-footer">
        <div>
          <strong>Recommended actions</strong>
          <span>{actions.length ? actions.join(", ") : "No action"}</span>
        </div>
        <div>
          <strong>Input quality</strong>
          <span>
            {result.input_quality.feature_count_received}/{result.input_quality.feature_count_expected} features
          </span>
        </div>
        <div>
          <strong>Safety</strong>
          <span>{warnings.length ? warnings.join(", ") : "No warnings"}</span>
        </div>
        <span className="ml-dry-run">DRY RUN · no hardware commands</span>
      </footer>
    </section>
  );
}
