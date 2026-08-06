from __future__ import annotations

import pandas as pd
import pytest

from ml.config import FEATURE_NAMES
from ml.data_loader import DatasetValidationError, validate_dataset


def _valid_frame() -> pd.DataFrame:
    values = {column: 0 for column in FEATURE_NAMES}
    values.update(
        {
            "window_start": pd.Timestamp("2026-07-20 09:00:00"),
            "window_end": pd.Timestamp("2026-07-20 09:05:00"),
            "date": pd.Timestamp("2026-07-20"),
            "ventilation_current": "OFF",
            "ble_dominant_side_estimate": "NO_SIGNAL",
            "co2_quality_flag": 0,
            "ble_quality_flag": 0,
            "humidity_mean_percent": 50,
            "ground_truth_occupancy": 0,
            "ground_truth_left_share": 0.5,
            "ground_truth_dominant_side": "BALANCED",
            "target_occupancy_plus_15m": 0,
            "target_occupancy_plus_30m": 0,
            "target_occupancy_plus_60m": 0,
            "target_co2_plus_30m_ppm": 450,
            "target_ventilation_plus_30m": "OFF",
            "target_overcrowded_plus_30m": 0,
        }
    )
    return pd.DataFrame([values])


def test_validate_dataset_accepts_required_contract():
    result = validate_dataset(_valid_frame())

    assert len(result) == 1
    assert result.loc[0, "pir_max_people_per_event"] == 0


def test_validate_dataset_rejects_missing_column():
    frame = _valid_frame().drop(columns=["co2_mean_ppm"])

    with pytest.raises(DatasetValidationError, match="co2_mean_ppm"):
        validate_dataset(frame)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("pir_max_people_per_event", 4, "PIR maximum"),
        ("radar_max_target_count", 4, "Radar maximum"),
        ("radar_mean_target_count", 3.1, "Radar mean"),
    ],
)
def test_validate_dataset_enforces_sensor_limits(column, value, message):
    frame = _valid_frame()
    frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value

    with pytest.raises(DatasetValidationError, match=message):
        validate_dataset(frame)
