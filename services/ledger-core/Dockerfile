# Build from the repo root: docker build -f services/ledger-core/Dockerfile .
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so source changes don't reinstall them.
COPY pyproject.toml uv.lock .python-version ./
COPY services/ledger-core/pyproject.toml services/ledger-core/
RUN uv sync --frozen --no-dev --package ledger-core --no-install-workspace

COPY services/ledger-core/src services/ledger-core/src
RUN uv sync --frozen --no-dev --package ledger-core --no-editable

FROM python:3.14-slim
RUN useradd --system --uid 10001 --no-create-home ledger
WORKDIR /app
COPY --from=build /app/.venv .venv
COPY services/ledger-core/alembic.ini alembic.ini
COPY services/ledger-core/migrations migrations
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER ledger
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=6 \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/readyz', timeout=2)"]
CMD ["uvicorn", "ledger_core.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "warning"]
