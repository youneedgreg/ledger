import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from ledger_core.config import Settings
from ledger_core.db_roles import set_role_passwords
from ledger_core.main import create_app

from .conftest import ROLE_PASSWORDS

pytestmark = pytest.mark.integration


def test_ready_when_postgres_is_reachable_as_ledger_app(
    migrated: str, migrator_url: str
) -> None:
    set_role_passwords(migrator_url, ROLE_PASSWORDS)
    params = conninfo_to_dict(migrator_url)
    params.update(user="ledger_app", password=ROLE_PASSWORDS["ledger_app"])
    app = create_app(Settings(database_url=make_conninfo(**params)))

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_unavailable_when_postgres_is_down_but_process_stays_alive() -> None:
    app = create_app(
        Settings(database_url="postgresql://nobody:nothing@127.0.0.1:1/none?connect_timeout=1")
    )

    with TestClient(app) as client:
        ready = client.get("/readyz")
        alive = client.get("/healthz")

    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable"}
    assert alive.status_code == 200
