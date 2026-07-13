from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.config import Config


def main() -> None:
    config = Config()
    app = create_app()

    print(f"  Backend : http://localhost:{config.port}")
    print(f"  Database: {config.database_path}")
    print(f"  Debug   : {config.debug}")

    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    main()
