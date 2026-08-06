from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import (
    FEATURE_NAMES,
    FUTURE_TARGET_COLUMNS,
    GROUND_TRUTH_COLUMNS,
)


STRUCTURAL_COLUMNS = ("window_start", "window_end", "date")
REQUIRED_COLUMNS = (
    *STRUCTURAL_COLUMNS,
    *FEATURE_NAMES,
    *GROUND_TRUTH_COLUMNS,
    *FUTURE_TARGET_COLUMNS,
)


class DatasetValidationError(ValueError):
    pass


def load_dataset(path: str | Path, sheet_name: str = "Dataset") -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Dataset not found: {source}")

    suffix = source.suffix.lower()
    if suffix == ".xlsx":
        frame = pd.read_excel(source, sheet_name=sheet_name)
    elif suffix == ".csv":
        frame = pd.read_csv(source)
    else:
        raise DatasetValidationError("Dataset must be an .xlsx or .csv file")

    return validate_dataset(frame)


def validate_required_columns(
    frame: pd.DataFrame,
    required_columns: Iterable[str] = REQUIRED_COLUMNS,
) -> None:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise DatasetValidationError(
            "Missing required dataset column(s): " + ", ".join(missing)
        )


def validate_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    validate_required_columns(frame)
    validated = frame.copy()

    for column in ("window_start", "window_end", "date"):
        validated[column] = pd.to_datetime(validated[column], errors="raise")
    validated["date"] = validated["date"].dt.normalize()

    if validated.empty:
        raise DatasetValidationError("Dataset is empty")
    if validated["window_start"].isna().any():
        raise DatasetValidationError("window_start contains missing values")
    if validated["window_start"].duplicated().any():
        raise DatasetValidationError("window_start contains duplicate records")
    if not validated["window_start"].is_monotonic_increasing:
        raise DatasetValidationError("Dataset must be ordered chronologically")
    if (validated["window_end"] <= validated["window_start"]).any():
        raise DatasetValidationError("window_end must be later than window_start")

    _validate_range(
        validated,
        "pir_max_people_per_event",
        minimum=0,
        maximum=3,
        message="PIR maximum people per event must be between 0 and 3",
    )
    _validate_range(
        validated,
        "radar_max_target_count",
        minimum=0,
        maximum=3,
        message="Radar maximum target count must be between 0 and 3",
    )
    _validate_range(
        validated,
        "radar_mean_target_count",
        minimum=0,
        maximum=3,
        message="Radar mean target count must be between 0 and 3",
    )
    _validate_range(
        validated,
        "humidity_mean_percent",
        minimum=0,
        maximum=100,
        message="Humidity must be between 0 and 100 percent",
    )

    if (validated["pir_total_detected_people"].dropna() < 0).any():
        raise DatasetValidationError("PIR total detected people must be non-negative")
    if (validated["ground_truth_occupancy"].dropna() < 0).any():
        raise DatasetValidationError("Ground-truth occupancy must be non-negative")

    for target in (
        "target_occupancy_plus_15m",
        "target_occupancy_plus_30m",
        "target_occupancy_plus_60m",
    ):
        if (validated[target].dropna() < 0).any():
            raise DatasetValidationError(f"{target} must be non-negative")

    return validated.reset_index(drop=True)


def dataset_summary(frame: pd.DataFrame) -> dict:
    return {
        "record_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "date_start": frame["date"].min().date().isoformat(),
        "date_end": frame["date"].max().date().isoformat(),
        "feature_count": len(FEATURE_NAMES),
        "pir_max_people_per_event": int(frame["pir_max_people_per_event"].max()),
        "pir_total_detected_people_max": int(
            frame["pir_total_detected_people"].max()
        ),
        "radar_max_target_count": int(frame["radar_max_target_count"].max()),
    }


def _validate_range(
    frame: pd.DataFrame,
    column: str,
    minimum: float,
    maximum: float,
    message: str,
) -> None:
    values = frame[column].dropna()
    if ((values < minimum) | (values > maximum)).any():
        raise DatasetValidationError(message)
