from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from ledger_core.db_roles import set_role_passwords

from .conftest import ROLE_PASSWORDS

pytestmark = pytest.mark.integration


def role_url(migrator_url: str, role: str) -> str:
    params = conninfo_to_dict(migrator_url)
    params.update(user=role, password=ROLE_PASSWORDS[role])
    return make_conninfo(**params)


@pytest.fixture
def roles_ready(migrated: str, migrator_url: str) -> None:
    set_role_passwords(migrator_url, ROLE_PASSWORDS)


@pytest.fixture
def probe_table(roles_ready: None, migrator_url: str) -> Iterator[None]:
    with psycopg.connect(migrator_url, autocommit=True) as connection:
        connection.execute("CREATE TABLE probe (id int)")
        connection.execute("INSERT INTO probe VALUES (1)")
        yield
        connection.execute("DROP TABLE probe")


@pytest.mark.parametrize("role", sorted(ROLE_PASSWORDS))
def test_service_roles_can_connect_but_not_change_the_schema(
    roles_ready: None, migrator_url: str, role: str
) -> None:
    with psycopg.connect(role_url(migrator_url, role)) as connection:
        assert connection.execute("SELECT current_user").fetchone() == (role,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("CREATE TABLE should_fail (id int)")


@pytest.mark.parametrize("role", sorted(ROLE_PASSWORDS))
def test_service_roles_have_no_elevated_attributes(
    roles_ready: None, migrator_url: str, role: str
) -> None:
    with psycopg.connect(migrator_url) as connection:
        attributes = connection.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = %s",
            (role,),
        ).fetchone()

    assert attributes == (False, False, False)


def test_reconciler_can_read_new_tables_but_not_write(
    probe_table: None, migrator_url: str
) -> None:
    with psycopg.connect(role_url(migrator_url, "ledger_reconciler")) as connection:
        assert connection.execute("SELECT id FROM probe").fetchone() == (1,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("INSERT INTO probe VALUES (2)")


@pytest.mark.parametrize("role", ["ledger_app", "ledger_relay"])
def test_other_roles_get_no_table_access_by_default(
    probe_table: None, migrator_url: str, role: str
) -> None:
    with psycopg.connect(role_url(migrator_url, role)) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT id FROM probe")


def test_wrong_password_is_rejected(roles_ready: None, migrator_url: str) -> None:
    params = conninfo_to_dict(migrator_url)
    params.update(user="ledger_app", password="wrong")

    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(make_conninfo(**params))


def test_setting_passwords_twice_is_safe(roles_ready: None, migrator_url: str) -> None:
    set_role_passwords(migrator_url, ROLE_PASSWORDS)

    with psycopg.connect(role_url(migrator_url, "ledger_app")) as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)


def test_migration_can_be_undone_and_reapplied(
    migrated: str, alembic_config: Config, migrator_url: str
) -> None:
    def existing_roles() -> set[str]:
        with psycopg.connect(migrator_url) as connection:
            rows = connection.execute(
                "SELECT rolname FROM pg_roles WHERE rolname LIKE 'ledger\\_%'"
                " AND rolname <> 'ledger_migrator'"
            ).fetchall()
        return {row[0] for row in rows}

    assert existing_roles() == set(ROLE_PASSWORDS)

    command.downgrade(alembic_config, "base")
    assert existing_roles() == set()

    command.upgrade(alembic_config, "head")
    assert existing_roles() == set(ROLE_PASSWORDS)
