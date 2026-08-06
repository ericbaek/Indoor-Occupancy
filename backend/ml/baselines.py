from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


class PersistenceBaseline:
    name = "persistence_current_estimate"

    def fit(self, frame: pd.DataFrame, target: Iterable[float] | None = None):
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        values = pd.to_numeric(frame["pir_cumulative_estimate"], errors="coerce")
        fallback = float(values.median()) if values.notna().any() else 0.0
        return values.fillna(fallback).to_numpy(dtype=float)


class SameWeekdayTimeBaseline:
    name = "same_weekday_time_average"
    keys = ("day_of_week_num", "hour", "minute")

    def __init__(self) -> None:
        self.lookup_: dict[tuple[int, int, int], float] = {}
        self.hour_lookup_: dict[tuple[int, int], float] = {}
        self.global_mean_: float = 0.0

    def fit(self, frame: pd.DataFrame, target: Iterable[float]):
        work = frame.loc[:, self.keys].copy()
        work["_target"] = np.asarray(target, dtype=float)
        grouped = work.groupby(list(self.keys), dropna=False)["_target"].mean()
        self.lookup_ = {
            tuple(int(value) for value in key): float(mean)
            for key, mean in grouped.items()
        }
        hour_grouped = work.groupby(["day_of_week_num", "hour"])["_target"].mean()
        self.hour_lookup_ = {
            (int(key[0]), int(key[1])): float(mean)
            for key, mean in hour_grouped.items()
        }
        self.global_mean_ = float(work["_target"].mean())
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        predictions = []
        for row in frame.loc[:, self.keys].itertuples(index=False, name=None):
            key = tuple(int(value) for value in row)
            value = self.lookup_.get(key)
            if value is None:
                value = self.hour_lookup_.get((key[0], key[1]), self.global_mean_)
            predictions.append(value)
        return np.asarray(predictions, dtype=float)


def recent_30_minute_average(frame: pd.DataFrame) -> np.ndarray:
    values = pd.to_numeric(frame["pir_cumulative_estimate"], errors="coerce")
    work = frame.assign(_estimate=values)
    rolling = work.groupby("date", sort=False)["_estimate"].transform(
        lambda series: series.rolling(window=6, min_periods=1).mean()
    )
    fallback = float(values.median()) if values.notna().any() else 0.0
    return rolling.fillna(fallback).to_numpy(dtype=float)


def ventilation_rule(
    predicted_occupancy: Iterable[float],
    co2_ppm: Iterable[float],
) -> np.ndarray:
    results: list[str] = []
    for occupancy, co2 in zip(predicted_occupancy, co2_ppm, strict=True):
        occ = float(occupancy)
        concentration = float(co2) if pd.notna(co2) else 0.0
        if concentration >= 1100 or occ >= 28:
            results.append("HIGH")
        elif concentration >= 800 or occ >= 16:
            results.append("MEDIUM")
        elif concentration >= 650 or occ >= 6:
            results.append("LOW")
        else:
            results.append("OFF")
    return np.asarray(results, dtype=object)
