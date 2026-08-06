from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import (
    CATEGORICAL_FEATURES,
    FEATURE_NAMES,
    FUTURE_TARGET_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    NUMERIC_FEATURES,
)


class LeakageError(ValueError):
    pass


def assert_no_leakage(
    feature_names: Iterable[str],
    frame: pd.DataFrame | None = None,
    target: str | None = None,
) -> None:
    names = tuple(feature_names)
    forbidden = set(FUTURE_TARGET_COLUMNS) | set(GROUND_TRUTH_COLUMNS)
    direct = [name for name in names if name in forbidden or name.startswith("target_")]
    future_time = [
        name
        for name in names
        if "future" in name.lower()
        or "forecast_time" in name.lower()
        or name.lower().endswith("_plus_30m")
        or name.lower().endswith("_plus_60m")
    ]
    if direct or future_time:
        invalid = sorted(set(direct + future_time))
        raise LeakageError("Leaking feature(s) detected: " + ", ".join(invalid))

    if frame is None or target is None or target not in frame.columns:
        return

    target_values = pd.to_numeric(frame[target], errors="coerce")
    for name in names:
        if name not in frame.columns:
            continue
        feature_values = pd.to_numeric(frame[name], errors="coerce")
        valid = feature_values.notna() & target_values.notna()
        if valid.sum() < 3:
            continue
        x = feature_values[valid].to_numpy(dtype=float)
        y = target_values[valid].to_numpy(dtype=float)
        if np.allclose(x, y, rtol=1e-12, atol=1e-12):
            raise LeakageError(f"Feature {name} is identical to target {target}")
        if np.std(x) > 0 and np.std(y) > 0:
            correlation = abs(float(np.corrcoef(x, y)[0, 1]))
            if correlation >= 0.999999:
                raise LeakageError(
                    f"Feature {name} is an almost exact transform of target {target}"
                )


def build_feature_frame(
    frame: pd.DataFrame,
    feature_names: Iterable[str] = FEATURE_NAMES,
) -> pd.DataFrame:
    names = tuple(feature_names)
    assert_no_leakage(names)
    result = frame.reindex(columns=names).copy()
    for column in NUMERIC_FEATURES:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def record_to_feature_frame(
    record: Mapping[str, object],
    feature_names: Iterable[str] = FEATURE_NAMES,
) -> pd.DataFrame:
    names = tuple(feature_names)
    assert_no_leakage(names)
    return build_feature_frame(pd.DataFrame([{name: record.get(name) for name in names}]), names)


def build_preprocessor(
    numeric_features: Iterable[str] = NUMERIC_FEATURES,
    categorical_features: Iterable[str] = CATEGORICAL_FEATURES,
    *,
    scale_numeric: bool = True,
) -> ColumnTransformer:
    numeric = list(numeric_features)
    categorical = list(categorical_features)
    numeric_steps: list[tuple[str, object]] = [
        ("imputer", SimpleImputer(strategy="median", add_indicator=True))
    ]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    return ColumnTransformer(
        transformers=[
            ("numeric", Pipeline(numeric_steps), numeric),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )


def missing_feature_ratio(record: Mapping[str, object]) -> float:
    missing = 0
    for name in FEATURE_NAMES:
        value = record.get(name)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            missing += 1
    return missing / len(FEATURE_NAMES)


def ble_activity_side(record: Mapping[str, object]) -> str:
    stated = str(record.get("ble_dominant_side_estimate") or "").upper()
    if stated in {"LEFT", "RIGHT", "BALANCED", "NO_SIGNAL"}:
        return stated

    left = _as_float(record.get("ble_left_rssi_mean_dbm"))
    right = _as_float(record.get("ble_right_rssi_mean_dbm"))
    if left is None and right is None:
        return "NO_SIGNAL"
    if left is None:
        return "RIGHT"
    if right is None:
        return "LEFT"
    difference = left - right
    if difference >= 5:
        return "LEFT"
    if difference <= -5:
        return "RIGHT"
    return "BALANCED"


def _as_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None
