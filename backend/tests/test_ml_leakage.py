from __future__ import annotations

import pandas as pd
import pytest

from ml.features import LeakageError, assert_no_leakage


def test_target_prefixed_feature_is_rejected():
    with pytest.raises(LeakageError, match="target_occupancy_plus_30m"):
        assert_no_leakage(["hour", "target_occupancy_plus_30m"])


def test_ground_truth_feature_is_rejected():
    with pytest.raises(LeakageError, match="ground_truth_occupancy"):
        assert_no_leakage(["ground_truth_occupancy"])


def test_linear_transform_of_target_is_rejected():
    frame = pd.DataFrame(
        {
            "suspicious": [3, 5, 7, 9],
            "target_occupancy_plus_30m": [1, 2, 3, 4],
        }
    )

    with pytest.raises(LeakageError, match="almost exact transform"):
        assert_no_leakage(
            ["suspicious"], frame, "target_occupancy_plus_30m"
        )
