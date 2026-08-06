"""Pure tests for windowed Bluetooth RSSI aggregation."""

from types import SimpleNamespace

import pytest

from scripts import ble_scanner


def _device(address="AA:BB:CC:DD:EE:01"):
    return SimpleNamespace(address=address)


def _advertisement(rssi=-55):
    return SimpleNamespace(rssi=rssi)


@pytest.mark.parametrize(
    ("rssi", "expected"),
    [(-120, 0.0), (-100, 0.0), (-70, 50.0), (-40, 100.0), (-20, 100.0)],
)
def test_rssi_to_score_is_clamped(rssi, expected):
    assert ble_scanner.rssi_to_score(rssi) == expected


def test_collect_observation_groups_same_address():
    observations = {}
    ble_scanner.collect_observation(_device(), _advertisement(-50), observations)
    ble_scanner.collect_observation(_device(), _advertisement(-60), observations)
    assert observations == {"AA:BB:CC:DD:EE:01": [-50.0, -60.0]}


@pytest.mark.parametrize("rssi", [None, True, -121, 1])
def test_collect_observation_ignores_invalid_rssi(rssi):
    observations = {}
    ble_scanner.collect_observation(_device(), _advertisement(rssi), observations)
    assert observations == {}


def test_window_uses_address_medians_then_strongest_three_median():
    summary = ble_scanner.summarise_window({
        "A": [-40, -50, -60],  # representative -50
        "B": [-55, -57, -53],  # representative -55
        "C": [-70],
        "D": [-90],
        "E": [-95],
    })
    assert summary["average_rssi"] == -55.0
    assert summary["signal_score"] == 75.0
    assert summary["observed_address_count"] == 5
    assert summary["strongest_signal_count"] == 3


def test_window_uses_all_signals_when_fewer_than_three():
    summary = ble_scanner.summarise_window({"A": [-48], "B": [-78]})
    assert summary["average_rssi"] == -63.0
    assert summary["signal_score"] == 61.67
    assert summary["strongest_signal_count"] == 2


def test_many_weak_addresses_do_not_change_top_three_result():
    baseline = ble_scanner.summarise_window({"A": [-48], "B": [-55], "C": [-63]})
    with_background = ble_scanner.summarise_window({
        "A": [-48],
        "B": [-55],
        "C": [-63],
        **{f"weak-{index}": [-100] for index in range(50)},
    })
    assert with_background["average_rssi"] == baseline["average_rssi"] == -55.0
    assert with_background["signal_score"] == baseline["signal_score"] == 75.0


def test_empty_window_is_zero_signal():
    summary = ble_scanner.summarise_window({})
    assert summary == {
        "average_rssi": None,
        "signal_score": 0.0,
        "observed_address_count": 0,
        "strongest_signal_count": 0,
    }


def test_window_rejects_zero_strongest_count():
    with pytest.raises(ValueError):
        ble_scanner.summarise_window({"A": [-50]}, strongest_count=0)


def test_payload_contains_no_device_count():
    summary = ble_scanner.summarise_window({"A": [-50]})
    payload = ble_scanner.build_payload("left-anchor", summary)
    assert payload["anchor_id"] == "left-anchor"
    assert payload["average_rssi"] == -50.0
    assert payload["signal_score"] == 83.33
    assert "observed_address_count" not in payload
    assert "device_count" not in payload
