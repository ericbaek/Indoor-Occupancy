from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, LinearRegression, LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight

from . import __version__
from .baselines import (
    PersistenceBaseline,
    SameWeekdayTimeBaseline,
    recent_30_minute_average,
    ventilation_rule,
)
from .config import (
    CATEGORICAL_FEATURES,
    DATASET_TYPE,
    DERIVED_FORECAST_FEATURE,
    EMPTY_30_SOURCE_TARGET,
    EMPTY_60_SOURCE_TARGET,
    FEATURE_NAMES,
    MODEL_VERSION,
    NUMERIC_FEATURES,
    OCCUPANCY_TARGET,
    OVERCROWDING_TARGET,
    VENTILATION_TARGET,
    TrainingConfig,
)
from .data_loader import dataset_summary, load_dataset
from .evaluate import (
    binary_metrics,
    occupancy_band_metrics,
    overfitting_warnings,
    regression_metrics,
    serialise_metrics,
    ventilation_metrics,
)
from .features import assert_no_leakage, build_feature_frame, build_preprocessor
from .split import ChronologicalSplits, chronological_split


def train_pipeline(
    dataset_path: str | Path,
    output_dir: str | Path,
    config: TrainingConfig | None = None,
) -> dict:
    settings = config or TrainingConfig()
    np.random.seed(settings.random_seed)

    frame = load_dataset(dataset_path)
    assert_no_leakage(FEATURE_NAMES, frame, OCCUPANCY_TARGET)
    splits = chronological_split(frame)

    occupancy = _train_occupancy(splits, settings)
    ventilation = _train_ventilation(splits, occupancy, settings)
    overcrowding = _train_overcrowding(splits, occupancy, settings)
    empty_30 = _train_empty_room(
        splits,
        occupancy,
        EMPTY_30_SOURCE_TARGET,
        "empty_30m",
        settings,
    )
    empty_60 = _train_empty_room(
        splits,
        occupancy,
        EMPTY_60_SOURCE_TARGET,
        "empty_60m",
        settings,
    )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    dates = splits.date_lists()
    metadata = {
        "model_name": occupancy["selected_name"],
        "model_version": MODEL_VERSION,
        "pipeline_version": __version__,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_type": DATASET_TYPE,
        "dataset_file": Path(dataset_path).name,
        "target": OCCUPANCY_TARGET,
        "feature_names": list(FEATURE_NAMES),
        "selected_occupancy_features": occupancy["selected_features"],
        "train_dates": dates["train"],
        "validation_dates": dates["validation"],
        "test_dates": dates["test"],
        "metrics": {
            "validation_mae": occupancy["selected_metrics"]["validation"]["mae"],
            "validation_rmse": occupancy["selected_metrics"]["validation"]["rmse"],
            "test_mae": occupancy["selected_metrics"]["test"]["mae"],
            "test_rmse": occupancy["selected_metrics"]["test"]["rmse"],
            "test_r2": occupancy["selected_metrics"]["test"]["r2"],
        },
        "dataset": dataset_summary(frame),
        "selection": {
            "occupancy": occupancy["selection"],
            "ventilation": ventilation["selection"],
            "overcrowding": overcrowding["selection"],
            "empty_30m": empty_30["selection"],
            "empty_60m": empty_60["selection"],
        },
        "overfitting_warnings": occupancy["overfitting_warnings"],
        "leakage_checks": {
            "target_prefixed_features": [],
            "future_timestamp_features": [],
            "ground_truth_production_features": [],
            "preprocessing_fit_scope": "train_only",
            "passed": True,
        },
        "important_features": occupancy["important_features"],
        "limitations": _limitations(overcrowding, ventilation),
    }

    metrics = {
        "occupancy": {
            "selected_model": occupancy["selected_name"],
            "selected_metrics": occupancy["selected_metrics"],
            "candidate_models": occupancy["candidate_metrics"],
            "baselines": occupancy["baseline_metrics"],
            "baseline_improvement_fraction": occupancy["baseline_improvement"],
            "occupancy_bands_validation": occupancy["band_metrics_validation"],
            "occupancy_bands_test": occupancy["band_metrics_test"],
            "overfitting_warnings": occupancy["overfitting_warnings"],
        },
        "ventilation": ventilation["metrics"],
        "overcrowding": overcrowding["metrics"],
        "empty_30m": empty_30["metrics"],
        "empty_60m": empty_60["metrics"],
    }

    bundle = {
        "model_version": MODEL_VERSION,
        "config": settings.to_dict(),
        "feature_names": list(FEATURE_NAMES),
        "occupancy": {
            "name": occupancy["selected_name"],
            "kind": occupancy["selected_kind"],
            "estimator": occupancy["selected_estimator"],
            "interval_half_width": occupancy["interval_half_width"],
            "base_confidence": occupancy["base_confidence"],
        },
        "ventilation": {
            "name": ventilation["selected_name"],
            "kind": ventilation["selected_kind"],
            "estimator": ventilation["selected_estimator"],
        },
        "overcrowding": {
            "name": overcrowding["selected_name"],
            "kind": overcrowding["selected_kind"],
            "estimator": overcrowding["selected_estimator"],
            "threshold": overcrowding["threshold"],
        },
        "empty_30m": {
            "name": empty_30["selected_name"],
            "estimator": empty_30["selected_estimator"],
            "threshold": empty_30["threshold"],
            "safety_validated": empty_30["safety_validated"],
        },
        "empty_60m": {
            "name": empty_60["selected_name"],
            "estimator": empty_60["selected_estimator"],
            "threshold": empty_60["threshold"],
            "safety_validated": empty_60["safety_validated"],
        },
    }

    joblib.dump(bundle, output / "model_bundle.joblib")
    _write_json(output / "metadata.json", metadata)
    _write_json(output / "training_config.json", settings.to_dict())
    _write_json(output / "feature_names.json", {"feature_names": list(FEATURE_NAMES)})
    _write_json(output / "metrics.json", metrics)

    return serialise_metrics(
        {
            "output_dir": str(output.resolve()),
            "metadata": metadata,
            "metrics": metrics,
        }
    )


def _train_occupancy(
    splits: ChronologicalSplits,
    config: TrainingConfig,
) -> dict:
    task = splits.for_target(OCCUPANCY_TARGET)
    feature_frames = {
        "train": build_feature_frame(task.train),
        "validation": build_feature_frame(task.validation),
        "test": build_feature_frame(task.test),
    }
    targets = {
        "train": task.train[OCCUPANCY_TARGET].to_numpy(dtype=float),
        "validation": task.validation[OCCUPANCY_TARGET].to_numpy(dtype=float),
        "test": task.test[OCCUPANCY_TARGET].to_numpy(dtype=float),
    }

    candidate_metrics: dict[str, dict] = {}
    candidate_estimators: dict[str, object] = {}
    for name, model in _regression_candidates(config).items():
        pipeline = Pipeline(
            [
                ("preprocessor", build_preprocessor()),
                ("model", model),
            ]
        )
        pipeline.fit(feature_frames["train"], targets["train"])
        candidate_estimators[name] = pipeline
        candidate_metrics[name] = {
            split_name: regression_metrics(
                targets[split_name],
                _clip(
                    pipeline.predict(feature_frames[split_name]),
                    config.maximum_predicted_occupancy,
                ),
            )
            for split_name in ("train", "validation", "test")
        }

    baseline_estimators: dict[str, object] = {}
    baseline_predictions: dict[str, dict[str, np.ndarray]] = {}

    persistence = PersistenceBaseline().fit(task.train, targets["train"])
    baseline_estimators[persistence.name] = persistence
    baseline_predictions[persistence.name] = {
        name: _clip(persistence.predict(getattr(task, name)), config.maximum_predicted_occupancy)
        for name in ("train", "validation", "test")
    }

    weekday = SameWeekdayTimeBaseline().fit(task.train, targets["train"])
    baseline_estimators[weekday.name] = weekday
    baseline_predictions[weekday.name] = {
        name: _clip(weekday.predict(getattr(task, name)), config.maximum_predicted_occupancy)
        for name in ("train", "validation", "test")
    }

    recent_name = "recent_30_minute_average"
    baseline_predictions[recent_name] = {
        name: _clip(
            recent_30_minute_average(getattr(task, name)),
            config.maximum_predicted_occupancy,
        )
        for name in ("train", "validation", "test")
    }
    baseline_metrics = {
        baseline_name: {
            split_name: regression_metrics(targets[split_name], predictions[split_name])
            for split_name in ("train", "validation", "test")
        }
        for baseline_name, predictions in baseline_predictions.items()
    }

    best_model_name = min(
        candidate_metrics,
        key=lambda name: candidate_metrics[name]["validation"]["rmse"],
    )
    best_baseline_name = min(
        baseline_metrics,
        key=lambda name: baseline_metrics[name]["validation"]["rmse"],
    )
    model_rmse = candidate_metrics[best_model_name]["validation"]["rmse"]
    baseline_rmse = baseline_metrics[best_baseline_name]["validation"]["rmse"]
    improvement = (baseline_rmse - model_rmse) / baseline_rmse

    if (
        improvement >= config.required_baseline_rmse_improvement
        or best_baseline_name == recent_name
    ):
        selected_name = best_model_name
        selected_kind = "model"
        selected_estimator = candidate_estimators[selected_name]
        selected_metrics = candidate_metrics[selected_name]
        predictions = {
            name: _clip(
                selected_estimator.predict(feature_frames[name]),
                config.maximum_predicted_occupancy,
            )
            for name in ("train", "validation", "test")
        }
        reason = (
            f"Selected {selected_name}: validation RMSE improved on the best "
            f"baseline by {improvement:.1%}."
        )
        selected_features = list(FEATURE_NAMES)
    else:
        selected_name = best_baseline_name
        selected_kind = "baseline"
        if selected_name == recent_name:
            raise RuntimeError("Recent-average baseline cannot be used for single-window inference")
        selected_estimator = baseline_estimators[selected_name]
        selected_metrics = baseline_metrics[selected_name]
        predictions = baseline_predictions[selected_name]
        reason = (
            f"Selected {selected_name}: the best ML candidate did not improve "
            f"validation RMSE by the required {config.required_baseline_rmse_improvement:.0%}."
        )
        selected_features = (
            list(SameWeekdayTimeBaseline.keys)
            if selected_name == weekday.name
            else ["pir_cumulative_estimate"]
        )

    validation_residuals = np.abs(targets["validation"] - predictions["validation"])
    interval_half_width = float(
        np.quantile(validation_residuals, config.prediction_interval_coverage)
    )
    base_confidence = float(
        np.clip(1.0 - interval_half_width / config.maximum_predicted_occupancy, 0.05, 0.99)
    )
    warnings = overfitting_warnings(selected_metrics)

    return {
        "task_splits": task,
        "selected_name": selected_name,
        "selected_kind": selected_kind,
        "selected_estimator": selected_estimator,
        "selected_metrics": selected_metrics,
        "selected_features": selected_features,
        "candidate_metrics": candidate_metrics,
        "baseline_metrics": baseline_metrics,
        "baseline_improvement": round(float(improvement), 4),
        "interval_half_width": round(interval_half_width, 4),
        "base_confidence": round(base_confidence, 4),
        "overfitting_warnings": warnings,
        "band_metrics_validation": occupancy_band_metrics(
            targets["validation"], predictions["validation"]
        ),
        "band_metrics_test": occupancy_band_metrics(targets["test"], predictions["test"]),
        "important_features": _important_features(selected_estimator, selected_features),
        "selection": {
            "selected": selected_name,
            "kind": selected_kind,
            "best_model": best_model_name,
            "best_baseline": best_baseline_name,
            "baseline_improvement_fraction": round(float(improvement), 4),
            "reason": reason,
        },
    }


def _train_ventilation(
    splits: ChronologicalSplits,
    occupancy: dict,
    config: TrainingConfig,
) -> dict:
    task = splits.for_target(VENTILATION_TARGET)
    task_frames = _forecast_feature_frames(task, occupancy, config)
    numeric = (*NUMERIC_FEATURES, DERIVED_FORECAST_FEATURE)
    target = {
        name: getattr(task, name)[VENTILATION_TARGET].astype(str).to_numpy()
        for name in ("train", "validation", "test")
    }

    majority_class = pd.Series(target["train"]).mode().iloc[0]
    rule_predictions = {
        name: ventilation_rule(
            task_frames[name][DERIVED_FORECAST_FEATURE],
            task_frames[name]["co2_mean_ppm"],
        )
        for name in ("train", "validation", "test")
    }
    majority_predictions = {
        name: np.full(len(values), majority_class, dtype=object)
        for name, values in target.items()
    }
    baseline_metrics = {
        "rule_based": {
            name: ventilation_metrics(target[name], rule_predictions[name])
            for name in target
        },
        "majority_class": {
            name: ventilation_metrics(target[name], majority_predictions[name])
            for name in target
        },
    }

    candidate_metrics: dict[str, dict] = {}
    estimators: dict[str, object] = {}
    for name, model in _classification_candidates(config).items():
        pipeline = Pipeline(
            [
                (
                    "preprocessor",
                    build_preprocessor(numeric, CATEGORICAL_FEATURES),
                ),
                ("model", model),
            ]
        )
        fit_kwargs = {}
        if isinstance(model, GradientBoostingClassifier):
            fit_kwargs["model__sample_weight"] = compute_sample_weight(
                class_weight="balanced", y=target["train"]
            )
        pipeline.fit(task_frames["train"], target["train"], **fit_kwargs)
        estimators[name] = pipeline
        candidate_metrics[name] = {
            split_name: ventilation_metrics(
                target[split_name], pipeline.predict(task_frames[split_name])
            )
            for split_name in ("train", "validation", "test")
        }

    best_name = max(
        candidate_metrics,
        key=lambda name: (
            candidate_metrics[name]["validation"]["macro_f1"],
            candidate_metrics[name]["validation"]["balanced_accuracy"],
        ),
    )
    best = candidate_metrics[best_name]["validation"]
    rule = baseline_metrics["rule_based"]["validation"]
    clearly_better = (
        best["macro_f1"] >= rule["macro_f1"] + 0.02
        and best["balanced_accuracy"] >= rule["balanced_accuracy"]
        and best["per_class"]["HIGH"]["recall"]
        >= rule["per_class"]["HIGH"]["recall"]
    )
    if clearly_better:
        selected_name = best_name
        selected_kind = "model"
        selected_estimator = estimators[best_name]
        reason = "ML classifier clearly improved validation macro F1 without reducing HIGH recall."
    else:
        selected_name = "rule_based"
        selected_kind = "rule"
        selected_estimator = estimators[best_name]
        reason = "Rule baseline retained because ML did not clearly improve validation safety metrics."

    return {
        "selected_name": selected_name,
        "selected_kind": selected_kind,
        "selected_estimator": selected_estimator,
        "selection": {
            "selected": selected_name,
            "best_ml_candidate": best_name,
            "reason": reason,
        },
        "metrics": {
            "selected": selected_name,
            "candidate_models": candidate_metrics,
            "baselines": baseline_metrics,
        },
    }


def _train_overcrowding(
    splits: ChronologicalSplits,
    occupancy: dict,
    config: TrainingConfig,
) -> dict:
    task = splits.for_target(OVERCROWDING_TARGET)
    task_frames = _forecast_feature_frames(task, occupancy, config)
    numeric = (*NUMERIC_FEATURES, DERIVED_FORECAST_FEATURE)
    target = {
        name: getattr(task, name)[OVERCROWDING_TARGET].astype(int).to_numpy()
        for name in ("train", "validation", "test")
    }
    candidate_metrics: dict[str, dict] = {}
    estimators: dict[str, object] = {}
    thresholds: dict[str, float] = {}

    for name, model in _binary_candidates(config).items():
        pipeline = Pipeline(
            [
                ("preprocessor", build_preprocessor(numeric, CATEGORICAL_FEATURES)),
                ("model", model),
            ]
        )
        fit_kwargs = {}
        if isinstance(model, GradientBoostingClassifier):
            fit_kwargs["model__sample_weight"] = compute_sample_weight(
                class_weight="balanced", y=target["train"]
            )
        pipeline.fit(task_frames["train"], target["train"], **fit_kwargs)
        estimators[name] = pipeline
        validation_probability = _positive_probability(
            pipeline, task_frames["validation"]
        )
        threshold = _recall_priority_threshold(target["validation"], validation_probability)
        thresholds[name] = threshold
        candidate_metrics[name] = {}
        for split_name in ("train", "validation", "test"):
            probability = _positive_probability(pipeline, task_frames[split_name])
            prediction = probability >= threshold
            candidate_metrics[name][split_name] = binary_metrics(
                target[split_name], prediction, probability
            )

    rule_metrics: dict[str, dict] = {}
    for split_name in ("train", "validation", "test"):
        forecast = task_frames[split_name][DERIVED_FORECAST_FEATURE].to_numpy(dtype=float)
        probability = _capacity_probability(forecast, config.room_capacity)
        prediction = forecast > config.room_capacity
        rule_metrics[split_name] = binary_metrics(
            target[split_name], prediction, probability
        )

    validation_has_positives = bool(target["validation"].sum())
    if validation_has_positives:
        best_name = max(
            candidate_metrics,
            key=lambda name: (
                candidate_metrics[name]["validation"]["recall"] or -1,
                candidate_metrics[name]["validation"]["f1"] or -1,
            ),
        )
        selected_name = best_name
        selected_kind = "model"
        threshold = thresholds[best_name]
        reason = "Classifier selected using validation recall and F1."
    else:
        best_name = "logistic_regression"
        selected_name = "rule_based_capacity"
        selected_kind = "rule"
        threshold = thresholds[best_name]
        reason = (
            "Capacity rule retained because validation contains no positive "
            "overcrowding examples; recall cannot be estimated."
        )

    return {
        "selected_name": selected_name,
        "selected_kind": selected_kind,
        "selected_estimator": estimators[best_name],
        "threshold": threshold,
        "selection": {
            "selected": selected_name,
            "validation_positive_count": int(target["validation"].sum()),
            "test_positive_count": int(target["test"].sum()),
            "reason": reason,
        },
        "metrics": {
            "selected": selected_name,
            "candidate_models": candidate_metrics,
            "rule_based_capacity": rule_metrics,
        },
    }


def _train_empty_room(
    splits: ChronologicalSplits,
    occupancy: dict,
    source_target: str,
    task_name: str,
    config: TrainingConfig,
) -> dict:
    task = splits.for_target(source_target)
    task_frames = _forecast_feature_frames(task, occupancy, config)
    numeric = (*NUMERIC_FEATURES, DERIVED_FORECAST_FEATURE)
    target = {
        name: (getattr(task, name)[source_target].to_numpy(dtype=float) == 0).astype(int)
        for name in ("train", "validation", "test")
    }
    estimators: dict[str, object] = {}
    thresholds: dict[str, float] = {}
    candidate_metrics: dict[str, dict] = {}

    for name, model in _binary_candidates(config).items():
        pipeline = Pipeline(
            [
                ("preprocessor", build_preprocessor(numeric, CATEGORICAL_FEATURES)),
                ("model", model),
            ]
        )
        fit_kwargs = {}
        if isinstance(model, GradientBoostingClassifier):
            fit_kwargs["model__sample_weight"] = compute_sample_weight(
                class_weight="balanced", y=target["train"]
            )
        pipeline.fit(task_frames["train"], target["train"], **fit_kwargs)
        estimators[name] = pipeline
        validation_probability = _positive_probability(pipeline, task_frames["validation"])
        threshold = _precision_priority_threshold(
            target["validation"], validation_probability, minimum_precision=0.85
        )
        thresholds[name] = threshold
        candidate_metrics[name] = {}
        for split_name in ("train", "validation", "test"):
            probability = _positive_probability(pipeline, task_frames[split_name])
            prediction = probability >= threshold
            candidate_metrics[name][split_name] = binary_metrics(
                target[split_name],
                prediction,
                probability,
                false_recommendation_name="false_empty_recommendation_count",
            )

    best_name = max(
        candidate_metrics,
        key=lambda name: (
            candidate_metrics[name]["validation"]["precision"] or -1,
            candidate_metrics[name]["validation"]["recall"] or -1,
            candidate_metrics[name]["validation"]["f1"] or -1,
        ),
    )
    selected_validation = candidate_metrics[best_name]["validation"]
    safety_validated = (
        (selected_validation["precision"] or 0.0) >= 0.85
        and (selected_validation["recall"] or 0.0) >= 0.75
    )
    reason = "Selected on validation precision first, then recall and F1."
    if not safety_validated:
        reason += " Automatic energy-saving recommendations remain disabled because validation safety targets were not met."
    return {
        "selected_name": best_name,
        "selected_estimator": estimators[best_name],
        "threshold": thresholds[best_name],
        "safety_validated": safety_validated,
        "selection": {
            "selected": best_name,
            "threshold": thresholds[best_name],
            "safety_validated": safety_validated,
            "reason": reason,
        },
        "metrics": {
            "selected": best_name,
            "source_target": source_target,
            "candidate_models": candidate_metrics,
        },
    }


def _forecast_feature_frames(
    task: ChronologicalSplits,
    occupancy: dict,
    config: TrainingConfig,
) -> dict[str, pd.DataFrame]:
    result = {}
    estimator = occupancy["selected_estimator"]
    for name in ("train", "validation", "test"):
        frame = getattr(task, name)
        features = build_feature_frame(frame)
        predicted = _clip(estimator.predict(features), config.maximum_predicted_occupancy)
        features[DERIVED_FORECAST_FEATURE] = predicted
        result[name] = features
    return result


def _regression_candidates(config: TrainingConfig) -> dict[str, object]:
    seed = config.random_seed
    return {
        "linear_regression": LinearRegression(),
        "ridge_regression": Ridge(alpha=10.0),
        "elastic_net": ElasticNet(
            alpha=0.03,
            l1_ratio=0.2,
            max_iter=10_000,
            random_state=seed,
        ),
        "random_forest_regressor": RandomForestRegressor(
            n_estimators=160,
            max_depth=8,
            min_samples_leaf=6,
            min_samples_split=12,
            max_features=0.7,
            random_state=seed,
            n_jobs=-1,
        ),
        "gradient_boosting_regressor": GradientBoostingRegressor(
            n_estimators=120,
            learning_rate=0.04,
            max_depth=3,
            min_samples_leaf=8,
            min_samples_split=16,
            loss="huber",
            random_state=seed,
        ),
    }


def _classification_candidates(config: TrainingConfig) -> dict[str, object]:
    seed = config.random_seed
    return {
        "logistic_regression": LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=seed,
        ),
        "random_forest_classifier": RandomForestClassifier(
            n_estimators=160,
            max_depth=7,
            min_samples_leaf=6,
            min_samples_split=12,
            max_features=0.7,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "gradient_boosting_classifier": GradientBoostingClassifier(
            n_estimators=120,
            learning_rate=0.04,
            max_depth=3,
            min_samples_leaf=8,
            min_samples_split=16,
            random_state=seed,
        ),
    }


def _binary_candidates(config: TrainingConfig) -> dict[str, object]:
    return _classification_candidates(config)


def _positive_probability(estimator, frame: pd.DataFrame) -> np.ndarray:
    probabilities = estimator.predict_proba(frame)
    classes = list(estimator.classes_)
    if 1 not in classes:
        return np.zeros(len(frame), dtype=float)
    return probabilities[:, classes.index(1)]


def _recall_priority_threshold(actual: np.ndarray, probability: np.ndarray) -> float:
    if actual.sum() == 0:
        return 0.5
    candidates = np.linspace(0.10, 0.90, 17)
    scored = []
    for threshold in candidates:
        metrics = binary_metrics(actual, probability >= threshold, probability)
        scored.append((metrics["recall"] or 0.0, metrics["f1"] or 0.0, threshold))
    return float(max(scored, key=lambda item: (item[0], item[1], item[2]))[2])


def _precision_priority_threshold(
    actual: np.ndarray,
    probability: np.ndarray,
    minimum_precision: float,
) -> float:
    candidates = np.linspace(0.30, 0.95, 27)
    scored = []
    for threshold in candidates:
        metrics = binary_metrics(actual, probability >= threshold, probability)
        precision = metrics["precision"] or 0.0
        recall = metrics["recall"] or 0.0
        f1 = metrics["f1"] or 0.0
        scored.append((precision, recall, f1, float(threshold)))
    safe = [item for item in scored if item[0] >= minimum_precision]
    if safe:
        return max(safe, key=lambda item: (item[1], item[2], item[0]))[3]
    return max(scored, key=lambda item: (item[2], item[0], item[1]))[3]


def _capacity_probability(forecast: np.ndarray, capacity: int) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(forecast - capacity) / 3.0))


def _clip(values, maximum: int) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 0.0, float(maximum))


def _important_features(estimator, selected_features: list[str]) -> list[dict]:
    if not isinstance(estimator, Pipeline):
        return [
            {"feature": feature, "importance": None}
            for feature in selected_features
        ]
    preprocessor = estimator.named_steps["preprocessor"]
    model = estimator.named_steps["model"]
    names = preprocessor.get_feature_names_out()
    if hasattr(model, "feature_importances_"):
        values = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "coef_"):
        coefficients = np.asarray(model.coef_, dtype=float)
        values = np.abs(coefficients) if coefficients.ndim == 1 else np.mean(np.abs(coefficients), axis=0)
    else:
        return []
    indexes = np.argsort(values)[::-1][:15]
    return [
        {"feature": str(names[index]), "importance": round(float(values[index]), 6)}
        for index in indexes
    ]


def _limitations(overcrowding: dict, ventilation: dict) -> list[str]:
    limitations = [
        "The workbook is labelled realistic_synthetic; performance is not evidence of real-room accuracy.",
        "CO2 is a delayed contextual signal and is not a direct people counter.",
        "BLE RSSI indicates relative activity only and is not converted to a person count.",
        "Recommendations are dry-run decision support and never send hardware commands.",
    ]
    if overcrowding["selection"]["validation_positive_count"] == 0:
        limitations.append(
            "Validation has no overcrowding-positive rows, so overcrowding recall and PR-AUC cannot be validated."
        )
    if ventilation["selected_kind"] == "rule":
        limitations.append(
            "Ventilation uses the transparent rule baseline because ML did not clearly improve validation safety metrics."
        )
    return limitations


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(serialise_metrics(value), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train predictive occupancy models")
    parser.add_argument("--dataset", required=True, help="Path to the .xlsx or .csv dataset")
    parser.add_argument("--output-dir", required=True, help="Directory for model artefacts")
    parser.add_argument("--room-capacity", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = TrainingConfig(room_capacity=args.room_capacity)
    result = train_pipeline(args.dataset, args.output_dir, config)
    metadata = result["metadata"]
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "model_name": metadata["model_name"],
                "model_version": metadata["model_version"],
                "metrics": metadata["metrics"],
                "selection": metadata["selection"],
                "overfitting_warnings": metadata["overfitting_warnings"],
                "metadata_file": str(Path(args.output_dir) / "metadata.json"),
                "metrics_file": str(Path(args.output_dir) / "metrics.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
