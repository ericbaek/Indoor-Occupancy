from __future__ import annotations

import pandas as pd

from ml.baselines import SameWeekdayTimeBaseline, ventilation_rule
from ml.config import TrainingConfig


def test_same_weekday_time_baseline_has_hour_fallback():
    train = pd.DataFrame(
        {
            "day_of_week_num": [0, 0],
            "hour": [9, 9],
            "minute": [0, 5],
        }
    )
    baseline = SameWeekdayTimeBaseline().fit(train, [2, 4])

    prediction = baseline.predict(
        pd.DataFrame({"day_of_week_num": [0], "hour": [9], "minute": [10]})
    )

    assert prediction[0] == 3


def test_ventilation_rule_uses_co2_or_occupancy_thresholds():
    result = ventilation_rule([2, 7, 18, 1], [500, 500, 500, 1200])
    assert result.tolist() == ["OFF", "LOW", "MEDIUM", "HIGH"]


def test_prediction_cap_is_configurable_from_capacity():
    assert TrainingConfig(room_capacity=30).maximum_predicted_occupancy == 45
