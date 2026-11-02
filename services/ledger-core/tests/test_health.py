import json

import pytest
from fastapi.testclient import TestClient

from ledger_core.config import Settings
from ledger_core.main import create_app


@pytest.fixture
def client() -> TestClient:
    # The lifespan never runs here, so nothing connects to this URL.
    return TestClient(create_app(Settings(database_url="postgresql://unused")))


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generates_a_request_id_when_none_is_sent(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.headers["request-id"].startswith("req_")


def test_keeps_a_valid_request_id_from_the_gateway(client: TestClient) -> None:
    response = client.get("/healthz", headers={"Request-Id": "req_abc-123"})

    assert response.headers["request-id"] == "req_abc-123"


def test_replaces_a_malformed_request_id(client: TestClient) -> None:
    response = client.get("/healthz", headers={"Request-Id": 'evil" injected="1'})

    assert response.headers["request-id"].startswith("req_")
    assert "evil" not in response.headers["request-id"]


def test_logs_one_json_line_per_request(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    client.get("/healthz", headers={"Request-Id": "req_log-test"})

    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert line["event"] == "request completed"
    assert line["service"] == "ledger-core"
    assert line["request_id"] == "req_log-test"
    assert line["status"] == 200
    assert line["level"] == "info"
