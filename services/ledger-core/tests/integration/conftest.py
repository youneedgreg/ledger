from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

SERVICE_ROOT = Path(__file__).parents[2]
ROLE_PASSWORDS = {
    "ledger_app": "app-test-password",
    "ledger_relay": "relay-test-password",
    "ledger_reconciler": "reconciler-test-password",
}


@pytest.fixture(scope="session")
def migrator_url() -> Iterator[str]:
    with PostgresContainer(
        "postgres:17-alpine",
        username="ledger_migrator",
        password="migrator-test-password",
        dbname="ledger",
        driver=None,
    ) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def alembic_config(migrator_url: str) -> Config:
    config = Config(SERVICE_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", migrator_url)
    return config


@pytest.fixture
def migrated(alembic_config: Config) -> str:
    command.upgrade(alembic_config, "head")
    return "head"
