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
