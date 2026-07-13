import os
import tempfile

import pytest

from app import create_app


@pytest.fixture(scope="session")
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_occupancy_")

    application = create_app(test_config={"TESTING": True, "DATABASE": db_path})

    yield application

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_room_state(client):
    client.post("/api/rooms/room_01/reset")
    yield
