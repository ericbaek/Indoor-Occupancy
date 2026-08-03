# Two-Windows-computer Bluetooth signal test

This test verifies relative Left/Right BLE signal intensity. It does **not**
verify a device count, person count, distance, or coordinate.

## Layout

| Computer | Position | Anchor ID |
|---|---|---|
| Main Windows PC | Left side | `left-anchor` |
| Second Windows laptop | Right side | `right-anchor` |

Start Docker on the Main PC, then start `ble_scanner.py` natively on both
computers using the commands in `../DOCKER_BLUETOOTH.md`.

## Verify scanner output

Every four seconds each terminal should print a line similar to:

```text
Window: RSSI=-55.0 dBm score=75.0/100 (top 3 of 12 addresses)
```

The address totals in parentheses are local debugging only. They are not sent
as a device count and do not control the heatmap colour.

## API check

In Postman:

```http
GET http://<MAIN_PC_IP>:5000/api/bluetooth/signal-strength
```

Both zones should have `status: active`. If a scanner is stopped for 15
seconds, its zone becomes `offline` with `signal_score: null`.

## Physical scenarios

1. Move active Bluetooth sources close to the Left PC. The Left score and red
   intensity should become higher.
2. Move the sources close to the Right laptop. The Right side should become
   stronger after EMA smoothing catches up.
3. Place the sources near the middle. Both scores and colours should be close;
   `stronger_zone` may be `balanced`.

Keep sources still for at least 15-20 seconds at each position so several
four-second scan windows contribute to the EMA.

## Calibration

If both computers are equally far from the same source but one consistently
reports weaker RSSI, set its Docker calibration offset. For example:

```text
BLE_LEFT_RSSI_OFFSET=0
BLE_RIGHT_RSSI_OFFSET=4
```

Then rerun `docker compose up --build -d` on the Main PC.
