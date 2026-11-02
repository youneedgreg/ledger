import os

from alembic import context
from sqlalchemy import create_engine, pool


def database_url() -> str:
    url = context.config.get_main_option("sqlalchemy.url") or os.environ["LEDGER_MIGRATOR_DATABASE_URL"]
    # SQLAlchemy defaults to psycopg2 for a plain postgresql:// URL.
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        # Migrations are plain SQL, so there's no metadata to autogenerate from.
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported.")

run_migrations()
