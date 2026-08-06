import { useCallback, useEffect, useRef, useState } from "react";
import type { ReportSummary, EvaluationMetric, ReportExport } from "../data";

// Point this at your Flask backend. Override with a Vite env var
// (VITE_API_BASE_URL in a .env file) if the backend runs somewhere else.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

/** Matches the `range` query param accepted by /api/reports/*. */
export type ReportRange = "24h" | "7d" | "30d" | "90d";

export const REPORT_RANGES: { value: ReportRange; label: string }[] = [
  { value: "24h", label: "24H" },
  { value: "7d", label: "7D" },
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
];

type RawSummary = {
  range_label: string;
  total_hours_tracked: number;
  avg_occupancy: number;
  peak_occupancy: number;
  peak_at: string | null;
  data_completeness_percent: number;
};

type RawMetric = {
  model: string;
  mae: number;
  rmse: number;
  fusion_gain_percent: number | null;
  sample_count: number;
};

type RawExport = {
  id: string;
  name: string;
  room: string;
  range_label: string;
  format: "csv" | "pdf";
  generated_at: string;
  size_kb: number;
};

export type ReportsData = {
  summary: ReportSummary | null;
  evaluationMetrics: EvaluationMetric[];
  exports: ReportExport[];
  isLoading: boolean;
  error: string | null;
  /** Absolute download URL for a given export id, valid for the current range. */
  downloadUrl: (exportId: string) => string;
  refresh: () => void;
};

function formatPeakAt(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function mapSummary(raw: RawSummary): ReportSummary {
  return {
    rangeLabel: raw.range_label,
    totalHoursTracked: raw.total_hours_tracked,
    avgOccupancy: raw.avg_occupancy,
    peakOccupancy: raw.peak_occupancy,
    peakAt: formatPeakAt(raw.peak_at),
    dataCompletenessPercent: raw.data_completeness_percent,
  };
}

function mapMetric(raw: RawMetric): EvaluationMetric {
  return {
    model: raw.model,
    mae: raw.mae,
    rmse: raw.rmse,
    fusionGainPercent: raw.fusion_gain_percent,
    sampleCount: raw.sample_count,
  };
}

function mapExport(raw: RawExport): ReportExport {
  return {
    id: raw.id,
    name: raw.name,
    room: raw.room,
    rangeLabel: raw.range_label,
    format: raw.format,
    generatedAt: raw.generated_at,
    sizeKb: raw.size_kb,
  };
}

/**
 * Live /api/reports/* data for the Reports page. Refetches whenever `range`
 * changes. Unlike useOccupancyData this isn't polled by default — reports
 * are historical, so a fetch on mount/range-change (plus manual refresh())
 * is enough.
 */
export function useReportsData(range: ReportRange): ReportsData {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [evaluationMetrics, setEvaluationMetrics] = useState<EvaluationMetric[]>([]);
  const [exports, setExports] = useState<ReportExport[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);
  const [refreshTick, setRefreshTick] = useState(0);

  const refresh = useCallback(() => setRefreshTick((t) => t + 1), []);

  useEffect(() => {
    cancelledRef.current = false;
    setIsLoading(true);

    async function fetchReports() {
      try {
        const [summaryRes, evalRes, exportsRes] = await Promise.all([
          fetch(`${API_BASE}/reports/summary?range=${range}`),
          fetch(`${API_BASE}/reports/evaluation?range=${range}`),
          fetch(`${API_BASE}/reports/exports?range=${range}`),
        ]);

        if (!summaryRes.ok) throw new Error(`reports/summary: ${summaryRes.status}`);
        if (!evalRes.ok) throw new Error(`reports/evaluation: ${evalRes.status}`);
        if (!exportsRes.ok) throw new Error(`reports/exports: ${exportsRes.status}`);

        const summaryJson: RawSummary = await summaryRes.json();
        const evalJson: { metrics: RawMetric[] } = await evalRes.json();
        const exportsJson: { exports: RawExport[] } = await exportsRes.json();

        if (cancelledRef.current) return;

        setSummary(mapSummary(summaryJson));
        setEvaluationMetrics((evalJson.metrics ?? []).map(mapMetric));
        setExports((exportsJson.exports ?? []).map(mapExport));
        setError(null);
      } catch (err) {
        if (cancelledRef.current) return;
        setError(err instanceof Error ? err.message : "Failed to fetch report data");
        console.error("useReportsData: fetch failed", err);
      } finally {
        if (!cancelledRef.current) setIsLoading(false);
      }
    }

    fetchReports();
    return () => {
      cancelledRef.current = true;
    };
  }, [range, refreshTick]);

  const downloadUrl = useCallback(
    (exportId: string) => `${API_BASE}/reports/exports/${encodeURIComponent(exportId)}/download?range=${range}`,
    [range]
  );

  return { summary, evaluationMetrics, exports, isLoading, error, downloadUrl, refresh };
}