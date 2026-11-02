from fastapi import FastAPI

from ledger_core.config import Settings
from ledger_core.logging import configure_logging
from ledger_core.middleware import RequestContextMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Ledger Core", version="0.1.0")
    app.add_middleware(RequestContextMiddleware)

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        """Liveness: the process is up. Doesn't touch the database."""
        return {"status": "ok"}

    return app


app = create_app()
