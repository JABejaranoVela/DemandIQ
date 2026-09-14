import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from demandiq.api.schemas import (
    ErrorResponse,
    HealthResponse,
    LoadResponse,
    LoadsResponse,
    ReadyResponse,
    SalesResponse,
)
from demandiq.config import Settings, configure_logging
from demandiq.db import IngestionLoad, Sale, make_engine
from demandiq.ingestion.m5 import ID_PATTERN

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings()
        configure_logging(config.log_level)
        app.state.engine = engine or make_engine(config)
        try:
            yield
        finally:
            if engine is None:
                app.state.engine.dispose()

    app = FastAPI(
        title="DemandIQ",
        version="0.1.0",
        description="Observed sales and ingestion traceability. Forecasting is planned.",
        lifespan=lifespan,
        responses={
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"location": list(e["loc"]), "message": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request",
                    "details": details,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 422: "validation_error", 503: "not_ready"}.get(
            exc.status_code, "http_error"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail), "details": []}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("database_request_failed error_type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "Database or schema unavailable",
                    "details": [],
                }
            },
        )

    router = APIRouter(prefix="/api/v1")

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    @router.get("/health", response_model=HealthResponse, tags=["health"])
    def health():
        """Liveness only. Does not claim that analytical results are current."""
        return HealthResponse()

    @router.get("/ready", response_model=ReadyResponse, tags=["health"])
    def ready(request: Request):
        with request.app.state.engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "0002":
                raise HTTPException(503, "Schema migration is required")
            connection.execute(select(IngestionLoad.id).limit(1))
        return ReadyResponse()

    @router.get("/loads", response_model=LoadsResponse, tags=["loads"])
    def loads(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        table = IngestionLoad.__table__
        with request.app.state.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(table)
                    .order_by(table.c.started_at.desc(), table.c.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
                .mappings()
                .all()
            )
        return {"items": rows, "limit": limit, "offset": offset}

    @router.get("/loads/{load_id}", response_model=LoadResponse, tags=["loads"])
    def load(request: Request, load_id: UUID):
        table = IngestionLoad.__table__
        with request.app.state.engine.connect() as connection:
            row = connection.execute(select(table).where(table.c.id == load_id)).mappings().first()
        if row is None:
            raise HTTPException(404, "Load not found")
        return row

    @router.get("/sales", response_model=SalesResponse, tags=["sales"])
    def sales(
        request: Request,
        item_id: Annotated[str, Query(pattern=ID_PATTERN)],
        store_id: Annotated[str, Query(pattern=ID_PATTERN)],
        start_date: date,
        end_date: date,
        limit: Annotated[int, Query(ge=1, le=2000)] = 500,
        after_date: date | None = None,
    ):
        """Inclusive date range. Missing observations are omitted, never filled with zero."""
        if end_date < start_date:
            raise HTTPException(422, "end_date must be on or after start_date")
        if after_date is not None and not start_date <= after_date <= end_date:
            raise HTTPException(422, "after_date must be within the requested date range")
        table = Sale.__table__
        statement = (
            select(table)
            .join(IngestionLoad, table.c.load_id == IngestionLoad.id)
            .where(
                table.c.item_id == item_id,
                table.c.store_id == store_id,
                table.c.date.between(start_date, end_date),
                IngestionLoad.status == "completed",
            )
        )
        if after_date is not None:
            statement = statement.where(table.c.date > after_date)
        with request.app.state.engine.connect() as connection:
            rows = (
                connection.execute(statement.order_by(table.c.date).limit(limit + 1))
                .mappings()
                .all()
            )
        more = len(rows) > limit
        items = rows[:limit]
        return {
            "item_id": item_id,
            "store_id": store_id,
            "start_date": start_date,
            "end_date": end_date,
            "items": items,
            "next_after_date": items[-1]["date"] if more else None,
        }

    app.include_router(router)
    return app
