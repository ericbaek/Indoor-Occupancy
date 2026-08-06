from __future__ import annotations

import pandas as pd

from ml.features import ble_activity_side, build_preprocessor, missing_feature_ratio


def test_preprocessor_statistics_are_fitted_on_train_only():
    train = pd.DataFrame(
        {
            "pir_entry_count": [1.0, None, 1.0],
            "ventilation_current": ["OFF", "OFF", "LOW"],
        }
    )
    validation = pd.DataFrame(
        {"pir_entry_count": [1000.0], "ventilation_current": ["HIGH"]}
    )
    preprocessor = build_preprocessor(
        ["pir_entry_count"], ["ventilation_current"]
    )

    preprocessor.fit(train)
    preprocessor.transform(validation)

    imputer = preprocessor.named_transformers_["numeric"].named_steps["imputer"]
    assert imputer.statistics_[0] == 1.0


def test_ble_activity_side_uses_stronger_rssi():
    assert ble_activity_side(
        {
            "ble_left_rssi_mean_dbm": -55,
            "ble_right_rssi_mean_dbm": -72,
        }
    ) == "LEFT"


def test_missing_feature_ratio_is_bounded():
    ratio = missing_feature_ratio({"hour": 12})
    assert 0 < ratio < 1
