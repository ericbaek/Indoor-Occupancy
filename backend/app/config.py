import os


class Config:
    host: str = os.environ.get("FLASK_HOST", "0.0.0.0")
    port: int = int(os.environ.get("FLASK_PORT", "5000"))
    debug: bool = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    database_path: str = os.environ.get("DATABASE_PATH", "instance/occupancy.db")
    cors_origins: list[str] = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if o.strip()
    ]
