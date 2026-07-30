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

    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    main()
