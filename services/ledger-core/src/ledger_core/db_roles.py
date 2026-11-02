"""Sets the service roles' passwords. Safe to run after every migration."""

import os
from collections.abc import Mapping

import psycopg
from psycopg import sql

ROLE_PASSWORD_ENV = {
    "ledger_app": "LEDGER_APP_DB_PASSWORD",
    "ledger_relay": "LEDGER_RELAY_DB_PASSWORD",
    "ledger_reconciler": "LEDGER_RECONCILER_DB_PASSWORD",
}


def set_role_passwords(migrator_url: str, passwords: Mapping[str, str]) -> None:
    with psycopg.connect(migrator_url) as connection:
        for role, password in passwords.items():
            # Sending a SCRAM verifier keeps the plaintext out of server logs.
            verifier = connection.pgconn.encrypt_password(
                password.encode(), role.encode(), b"scram-sha-256"
            )
            connection.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(verifier.decode())
                )
            )


def main() -> None:
    set_role_passwords(
        os.environ["LEDGER_MIGRATOR_DATABASE_URL"],
        {role: os.environ[env] for role, env in ROLE_PASSWORD_ENV.items()},
    )


if __name__ == "__main__":
    main()
