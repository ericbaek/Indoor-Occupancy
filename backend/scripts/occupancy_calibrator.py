from __future__ import annotations

import argparse
import os
import sys

import requests


def api_base(backend_url: str) -> str:
    base = backend_url.rstrip("/")
    return base if base.endswith("/api") else f"{base}/api"


def get_occupancy(base: str) -> int:
    response = requests.get(f"{base}/occupancy/current", timeout=5)
    response.raise_for_status()
    return int(response.json()["occupancy"])


def calibrate(base: str, payload: dict[str, int]) -> dict:
    response = requests.post(
        f"{base}/occupancy/calibrate",
        json=payload,
        timeout=5,
    )
    if not response.ok:
        try:
            message = response.json().get("error", response.text)
        except ValueError:
            message = response.text
        raise RuntimeError(f"Backend returned {response.status_code}: {message}")
    return response.json()["data"]


def read_key() -> str:
    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            return {"H": "up", "P": "down"}.get(msvcrt.getwch(), "")
        return key

    import termios
    import tty

    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        key = sys.stdin.read(1)
        if key == "\x1b":
            sequence = sys.stdin.read(2)
            return {"[A": "up", "[B": "down"}.get(sequence, "")
        return key
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def show_result(data: dict) -> None:
    print(
        f"\rOccupancy: {data['previous_occupancy']} -> {data['occupancy']} "
        f"(calibration {data['count_change']:+d})          "
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Keyboard occupancy calibration")
    parser.add_argument(
        "--url",
        default=os.environ.get("OCCUPANCY_BACKEND_URL", "http://localhost:5000"),
        help="Backend base URL",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--set", type=int, dest="target", help="Set an exact occupancy and exit")
    action.add_argument("--delta", type=int, help="Apply one occupancy delta and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = api_base(args.url)

    try:
        if args.target is not None:
            show_result(calibrate(base, {"occupancy": args.target}))
            return
        if args.delta is not None:
            show_result(calibrate(base, {"delta": args.delta}))
            return

        current = get_occupancy(base)
        print(f"Backend: {base}")
        print("+ / Up: add 1    - / Down: remove 1    S: set number    R: refresh    Q: quit")
        print(f"Occupancy: {current}")

        while True:
            key = read_key()
            if key in ("q", "Q", "\x03"):
                print("\nStopped.")
                return
            if key in ("+", "=", "up"):
                show_result(calibrate(base, {"delta": 1}))
            elif key in ("-", "_", "down"):
                show_result(calibrate(base, {"delta": -1}))
            elif key in ("r", "R"):
                print(f"\rOccupancy: {get_occupancy(base)}                    ")
            elif key in ("s", "S"):
                raw_value = input("\nSet occupancy (0-1000): ").strip()
                try:
                    target = int(raw_value)
                except ValueError:
                    print("Enter a whole number.")
                    continue
                show_result(calibrate(base, {"occupancy": target}))
    except (requests.RequestException, RuntimeError, KeyError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
