import argparse
import os
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.config import Config


def _start_serial_thread(port: str, baudrate: int, backend_url: str) -> None:
    from hardware_gateway import _run_serial  # noqa: PLC0415

    def _run() -> None:
        time.sleep(2)
        _run_serial(port, baudrate, backend_url)

    threading.Thread(target=_run, daemon=True, name="serial-gateway").start()
    print(f"  Gateway : serial {port} @ {baudrate} baud → {backend_url}")


def _start_keyboard_controls(port: int) -> None:
    if not sys.stdin.isatty():
        print("  Keyboard: disabled (interactive terminal required)")
        return

    from occupancy_calibrator import run_backend_prompt

    def _run() -> None:
        try:
            run_backend_prompt(f"http://127.0.0.1:{port}", wait_seconds=15)
        except Exception as error:
            print(f"  Keyboard controls stopped: {error}")

    threading.Thread(
        target=_run,
        daemon=True,
        name="occupancy-keyboard-controls",
    ).start()
    print("  Keyboard: occupancy commands enabled in this terminal")


def _parse_args() -> argparse.Namespace:
    default_url = os.environ.get("BACKEND_URL", "http://localhost:5000")
    parser = argparse.ArgumentParser(
        description="Run the Flask backend (optionally with the serial gateway)."
    )
    parser.add_argument(
        "--serial-port",
        default=None,
        help="Serial port for the hardware gateway, e.g. COM5 or /dev/ttyS5.",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Serial baud rate (default: 115200)",
    )
    parser.add_argument(
        "--url",
        default=default_url,
        help=f"Backend base URL used by the gateway (default: {default_url})",
    )
    parser.add_argument(
        "--no-keyboard-controls",
        action="store_true",
        help="Disable occupancy keyboard controls in the backend terminal.",
    )
    return parser.parse_args()


def main() -> None:
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    args = _parse_args()
    config = Config()
    app = create_app()

    print(f"  Backend : http://localhost:{config.port}")
    print(f"  Database: {config.database_path}")
    print(f"  Debug   : {config.debug}")

    if args.serial_port:
        _start_serial_thread(args.serial_port, args.baudrate, args.url)

    reloader_process = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not args.no_keyboard_controls and (not config.debug or reloader_process):
        _start_keyboard_controls(config.port)

    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    main()
