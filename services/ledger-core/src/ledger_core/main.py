from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
import structlog
from fastapi import FastAPI, Response, status
from psycopg_pool import AsyncConnectionPool

from ledger_core.config import Settings
from ledger_core.logging import configure_logging
from ledger_core.middleware import RequestContextMiddleware

READINESS_TIMEOUT_SECONDS = 2.0

log = structlog.get_logger()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    pool = AsyncConnectionPool(
        settings.database_url.get_secret_value(), min_size=1, max_size=10, open=False
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Don't wait for a connection: the process should still start, and report
        # itself as not ready, while Postgres is down.
        await pool.open(wait=False)
        yield
        await pool.close()

    app = FastAPI(title="Ledger Core", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        """Liveness: the process is up. Doesn't touch the database."""
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz(response: Response) -> dict[str, str]:
        """Readiness: the service can reach Postgres."""
        try:
            async with pool.connection(timeout=READINESS_TIMEOUT_SECONDS) as connection:
                await connection.execute("SELECT 1")
        except psycopg.Error as error:
            log.warning("database unavailable", error_type=type(error).__name__)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unavailable"}
        return {"status": "ready"}

    return app
