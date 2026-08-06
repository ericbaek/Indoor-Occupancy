from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import (
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    VALIDATION_END,
    VALIDATION_START,
)


@dataclass(frozen=True)
class ChronologicalSplits:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame

    def for_target(self, target: str) -> "ChronologicalSplits":
        return ChronologicalSplits(
            self.train.dropna(subset=[target]).copy(),
            self.validation.dropna(subset=[target]).copy(),
            self.test.dropna(subset=[target]).copy(),
        )

    def date_lists(self) -> dict[str, list[str]]:
        return {
            "train": _date_list(self.train),
            "validation": _date_list(self.validation),
            "test": _date_list(self.test),
        }


def chronological_split(frame: pd.DataFrame) -> ChronologicalSplits:
    if "date" not in frame.columns:
        raise ValueError("date column is required for chronological splitting")

    dates = pd.to_datetime(frame["date"]).dt.normalize()
    train = frame[dates.between(TRAIN_START, TRAIN_END)].copy()
    validation = frame[
        dates.between(VALIDATION_START, VALIDATION_END)
    ].copy()
    test = frame[dates.between(TEST_START, TEST_END)].copy()

    if train.empty or validation.empty or test.empty:
        raise ValueError("Train, validation, and test splits must all be non-empty")

    splits = ChronologicalSplits(train, validation, test)
    assert_disjoint_dates(splits)
    return splits


def assert_disjoint_dates(splits: ChronologicalSplits) -> None:
    train_dates = set(pd.to_datetime(splits.train["date"]).dt.date)
    validation_dates = set(pd.to_datetime(splits.validation["date"]).dt.date)
    test_dates = set(pd.to_datetime(splits.test["date"]).dt.date)

    if train_dates & validation_dates:
        raise ValueError("Train and validation dates overlap")
    if train_dates & test_dates:
        raise ValueError("Train and test dates overlap")
    if validation_dates & test_dates:
        raise ValueError("Validation and test dates overlap")

    if max(train_dates) >= min(validation_dates):
        raise ValueError("Training dates must precede validation dates")
    if max(validation_dates) >= min(test_dates):
        raise ValueError("Validation dates must precede test dates")


def _date_list(frame: pd.DataFrame) -> list[str]:
    values = pd.to_datetime(frame["date"]).dt.date.unique()
    return sorted(value.isoformat() for value in values)
