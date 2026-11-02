"""Create least-privilege database roles (design doc section 9, threat E1).

The migrator role runs this migration and owns every table. Later migrations
grant each service role exactly the table privileges it needs, so a compromised
service can't change the schema or rewrite history.

Roles are created without passwords, which keeps secrets out of migrations.
`python -m ledger_core.db_roles` sets them for each environment.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SERVICE_ROLES = ("ledger_app", "ledger_relay", "ledger_reconciler")
ROLE_LIST = ", ".join(SERVICE_ROLES)


def upgrade() -> None:
    for role in SERVICE_ROLES:
        # Roles belong to the cluster, so they can outlive a dropped database.
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                    CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
                END IF;
            END
            $$
        """)

    op.execute(f"""
        DO $$
        BEGIN
            EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO {ROLE_LIST}', current_database());
        END
        $$
    """)
    op.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_LIST}")

    # The reconciler can read every table the migrator creates from now on.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ledger_reconciler"
    )


def downgrade() -> None:
    for role in SERVICE_ROLES:
        # Removes this role's grants and default privileges in this database.
        op.execute(f"DROP OWNED BY {role}")
        op.execute(f"DROP ROLE {role}")
    op.execute("GRANT USAGE ON SCHEMA public TO PUBLIC")
    op.execute("""
        DO $$
        BEGIN
            EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO PUBLIC', current_database());
        END
        $$
    """)
