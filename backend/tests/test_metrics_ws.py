from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_metrics_websocket_requires_token() -> None:
    with client.websocket_connect(f"/api/services/{uuid4()}/metrics") as websocket:
        message = websocket.receive()
        assert message["type"] == "websocket.close"
        assert message["code"] == 4401
