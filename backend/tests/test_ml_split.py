from __future__ import annotations

import pandas as pd

from ml.split import chronological_split


def test_chronological_split_uses_whole_non_overlapping_dates():
    dates = pd.date_range("2026-07-20", "2026-08-02", freq="D")
    frame = pd.DataFrame({"date": dates, "value": range(len(dates))})

    splits = chronological_split(frame)

    assert len(splits.train) == 9
    assert len(splits.validation) == 2
    assert len(splits.test) == 3
    assert splits.date_lists()["validation"] == ["2026-07-29", "2026-07-30"]
