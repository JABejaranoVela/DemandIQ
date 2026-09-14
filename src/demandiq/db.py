from datetime import date as DateValue
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from demandiq.config import Settings


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class IngestionLoad(Base):
    __tablename__ = "ingestion_loads"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="status"),
        CheckConstraint(
            "records_processed >= 0 AND records_rejected >= 0 AND records_inserted >= 0 "
            "AND records_unchanged >= 0",
            name="counts",
        ),
        Index(
            "uq_completed_fingerprint",
            "fingerprint",
            unique=True,
            postgresql_where=text("status = 'completed' AND reused_load_id IS NULL"),
        ),
        {"schema": "raw"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    reused_load_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw.ingestion_loads.id"))
    parser_version: Mapped[str] = mapped_column(String(30))
    selection: Mapped[dict] = mapped_column(JSONB)
    sources: Mapped[list] = mapped_column(JSONB)
    records_processed: Mapped[int] = mapped_column(BigInteger, default=0)
    records_rejected: Mapped[int] = mapped_column(BigInteger, default=0)
    records_inserted: Mapped[int] = mapped_column(BigInteger, default=0)
    records_unchanged: Mapped[int] = mapped_column(BigInteger, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(String(500))


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"schema": "core"}
    item_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    department_id: Mapped[str] = mapped_column(String(100))
    category_id: Mapped[str] = mapped_column(String(100))


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = {"schema": "core"}
    store_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    state_id: Mapped[str] = mapped_column(String(100))


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("units_sold >= 0", name="nonnegative_units"),
        Index("ix_sales_load_id", "load_id"),
        {"schema": "core"},
    )
    item_id: Mapped[str] = mapped_column(ForeignKey("core.products.item_id"), primary_key=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("core.stores.store_id"), primary_key=True)
    date: Mapped[DateValue] = mapped_column(primary_key=True)
    units_sold: Mapped[int] = mapped_column(BigInteger)
    load_id: Mapped[UUID] = mapped_column(ForeignKey("raw.ingestion_loads.id"))


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.connection_url(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="status"),
        CheckConstraint("horizon = 14", name="horizon"),
        Index("ix_forecast_runs_completed", "status", "finished_at"),
        {"schema": "analytics"},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None]
    source: Mapped[str] = mapped_column(String(40))
    source_loads: Mapped[list] = mapped_column(JSONB)
    data_fingerprint: Mapped[str | None] = mapped_column(String(64))
    selection: Mapped[dict] = mapped_column(JSONB)
    train_start: Mapped[DateValue]
    train_end: Mapped[DateValue]
    cutoff: Mapped[DateValue]
    horizon: Mapped[int]
    protocol_version: Mapped[str] = mapped_column(String(20))
    features_version: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(40))
    configuration: Mapped[dict] = mapped_column(JSONB)
    random_state: Mapped[int]
    versions: Mapped[dict] = mapped_column(JSONB)
    selected_method: Mapped[str | None] = mapped_column(String(40))
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[dict | None] = mapped_column(JSONB)
    stages: Mapped[list] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(String(500))
    error_details: Mapped[dict | None] = mapped_column(JSONB)


class ForecastPrediction(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        CheckConstraint("horizon_step BETWEEN 1 AND 14", name="horizon_step"),
        CheckConstraint(
            "predicted_units >= 0 AND predicted_units < 'Infinity'::float8",
            name="finite_prediction",
        ),
        CheckConstraint(
            "actual_units >= 0 AND actual_units < 'Infinity'::float8", name="finite_actual"
        ),
        {"schema": "analytics"},
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics.forecast_runs.id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String(20), primary_key=True)
    method: Mapped[str] = mapped_column(String(40), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    target_date: Mapped[DateValue] = mapped_column(primary_key=True)
    cutoff: Mapped[DateValue]
    horizon_step: Mapped[int]
    predicted_units: Mapped[float]
    actual_units: Mapped[float]
    volume_segment: Mapped[str] = mapped_column(String(10))
    intermittency_segment: Mapped[str] = mapped_column(String(10))


class ForecastMetric(Base):
    __tablename__ = "forecast_metrics"
    __table_args__ = (
        CheckConstraint(
            "(status = 'defined' AND value IS NOT NULL AND denominator > 0) OR "
            "(status = 'undefined' AND value IS NULL AND denominator = 0)",
            name="defined",
        ),
        {"schema": "analytics"},
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics.forecast_runs.id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String(20), primary_key=True)
    method: Mapped[str] = mapped_column(String(40), primary_key=True)
    scope: Mapped[str] = mapped_column(String(20), primary_key=True)
    scope_value: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(20), primary_key=True)
    value: Mapped[float | None]
    numerator: Mapped[float]
    denominator: Mapped[float]
    status: Mapped[str] = mapped_column(String(12))
