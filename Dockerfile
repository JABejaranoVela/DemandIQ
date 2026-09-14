FROM ghcr.io/astral-sh/uv:0.11.18 AS uv
FROM python:3.13-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd --gid 10001 demandiq && useradd --uid 10001 --gid 10001 --no-create-home demandiq \
    && mkdir -p /app/data/archive /app/artifacts/forecasting \
    && chown -R demandiq:demandiq /app/data /app/artifacts
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini uv.lock ./
COPY alembic ./alembic
USER demandiq
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=3)"
CMD ["uvicorn", "demandiq.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
