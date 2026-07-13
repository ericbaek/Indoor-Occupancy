def test_health_returns_200(client):
    assert client.get("/api/health").status_code == 200


def test_health_returns_ok_status(client):
    assert client.get("/api/health").get_json()["status"] == "ok"


def test_health_returns_database_connected(client):
    assert client.get("/api/health").get_json()["database"] == "connected"
