from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    precision_recall_fscore_support,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

from .config import VENTILATION_LEVELS


def regression_metrics(y_true: Iterable[float], y_pred: Iterable[float]) -> dict:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    return {
        "mae": _round(mean_absolute_error(actual, predicted)),
        "rmse": _round(math.sqrt(mean_squared_error(actual, predicted))),
        "r2": _round(r2_score(actual, predicted)),
        "median_absolute_error": _round(median_absolute_error(actual, predicted)),
        "sample_count": int(len(actual)),
    }


def occupancy_band_metrics(
    y_true: Iterable[float],
    y_pred: Iterable[float],
) -> dict[str, dict | None]:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    bands = {
        "0": actual == 0,
        "1-5": (actual >= 1) & (actual <= 5),
        "6-15": (actual >= 6) & (actual <= 15),
        "16-25": (actual >= 16) & (actual <= 25),
        "26+": actual >= 26,
    }
    result: dict[str, dict | None] = {}
    for name, mask in bands.items():
        result[name] = regression_metrics(actual[mask], predicted[mask]) if mask.any() else None
    return result


def ventilation_metrics(
    y_true: Iterable[str],
    y_pred: Iterable[str],
) -> dict:
    actual = np.asarray(y_true, dtype=object)
    predicted = np.asarray(y_pred, dtype=object)
    labels = list(VENTILATION_LEVELS)
    precision, recall, f1, support = precision_recall_fscore_support(
        actual,
        predicted,
        labels=labels,
        zero_division=0,
    )
    per_class = {
        label: {
            "precision": _round(precision[index]),
            "recall": _round(recall[index]),
            "f1": _round(f1[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    }
    present_recalls = recall[support > 0]
    return {
        "accuracy": _round(accuracy_score(actual, predicted)),
        "balanced_accuracy": _round(np.mean(present_recalls)),
        "macro_precision": _round(
            precision_score(actual, predicted, average="macro", zero_division=0)
        ),
        "macro_recall": _round(
            recall_score(actual, predicted, average="macro", zero_division=0)
        ),
        "macro_f1": _round(f1_score(actual, predicted, average="macro", zero_division=0)),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(actual, predicted, labels=labels).tolist(),
        "labels": labels,
        "false_negatives_high": int(
            ((actual == "HIGH") & (predicted != "HIGH")).sum()
        ),
        "sample_count": int(len(actual)),
    }


def binary_metrics(
    y_true: Iterable[int | bool],
    y_pred: Iterable[int | bool],
    probability: Iterable[float] | None = None,
    *,
    false_recommendation_name: str = "false_positive_count",
) -> dict:
    actual = np.asarray(y_true, dtype=int)
    predicted = np.asarray(y_pred, dtype=int)
    matrix = confusion_matrix(actual, predicted, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    result = {
        "precision": _safe_binary_metric(precision_score, actual, predicted),
        "recall": _safe_binary_metric(recall_score, actual, predicted),
        "f1": _safe_binary_metric(f1_score, actual, predicted),
        "false_negative_count": int(fn),
        false_recommendation_name: int(fp),
        "confusion_matrix": matrix.tolist(),
        "sample_count": int(len(actual)),
        "positive_count": int(actual.sum()),
    }

    if probability is not None and len(np.unique(actual)) == 2:
        scores = np.asarray(probability, dtype=float)
        result["pr_auc"] = _round(average_precision_score(actual, scores))
        result["roc_auc"] = _round(roc_auc_score(actual, scores))
    else:
        result["pr_auc"] = None
        result["roc_auc"] = None
    return result


def overfitting_warnings(metrics: dict[str, dict]) -> list[str]:
    train = metrics["train"]
    validation = metrics["validation"]
    test = metrics["test"]
    warnings: list[str] = []
    if validation["rmse"] >= train["rmse"] * 1.25:
        warnings.append("VALIDATION_RMSE_25_PERCENT_ABOVE_TRAIN")
    if test["rmse"] >= validation["rmse"] * 1.20:
        warnings.append("TEST_RMSE_20_PERCENT_ABOVE_VALIDATION")
    if train["r2"] - test["r2"] >= 0.15:
        warnings.append("TRAIN_TEST_R2_GAP_AT_LEAST_0_15")
    return warnings


def serialise_metrics(value):
    if isinstance(value, dict):
        return {str(key): serialise_metrics(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialise_metrics(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def _safe_binary_metric(function, actual: np.ndarray, predicted: np.ndarray):
    if actual.sum() == 0:
        return None
    return _round(function(actual, predicted, zero_division=0))


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)
