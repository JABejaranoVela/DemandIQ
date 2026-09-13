import csv
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy import Connection, Engine, insert, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from demandiq.config import Settings
from demandiq.db import IngestionLoad, Product, Sale, Store
from demandiq.ingestion.archive import archive_source
from demandiq.ingestion.m5 import (
    PARSER_VERSION,
    InputError,
    Selection,
    fingerprint,
    iter_sales,
    read_calendar,
)

logger = logging.getLogger(__name__)
INGESTION_LOCK = 481901337


@dataclass(frozen=True)
class LoadResult:
    load_id: UUID
    records_processed: int
    records_inserted: int
    records_unchanged: int
    reused_load_id: UUID | None = None


class IngestionFailed(Exception):
    def __init__(self, load_id: UUID, code: str, message: str):
        super().__init__(message)
        self.load_id = load_id
        self.code = code


def _dimensions(connection: Connection, frame: pd.DataFrame) -> None:
    definitions = (
        (
            Product.__table__,
            "item_id",
            {"item_id": "item_id", "dept_id": "department_id", "cat_id": "category_id"},
        ),
        (Store.__table__, "store_id", {"store_id": "store_id", "state_id": "state_id"}),
    )
    for table, key, names in definitions:
        values = frame[list(names)].drop_duplicates().rename(columns=names)
        if values[key].duplicated().any():
            raise InputError(
                "metadata_conflict", "Inconsistent metadata for a selected product or store", 1
            )
        rows = values.to_dict(orient="records")
        existing = {
            row[key]: dict(row)
            for row in connection.execute(
                select(table).where(table.c[key].in_(values[key].tolist()))
            ).mappings()
        }
        for row in rows:
            if row[key] in existing and existing[row[key]] != row:
                raise InputError(
                    "correction_not_supported",
                    "Existing product/store metadata differs; no data was overwritten",
                    1,
                )
        connection.execute(pg_insert(table).on_conflict_do_nothing(index_elements=[key]), rows)


def _persist_sales(connection: Connection, frame: pd.DataFrame, load_id: UUID) -> tuple[int, int]:
    _dimensions(connection, frame)
    inserted = unchanged = 0
    table = Sale.__table__
    for offset in range(0, len(frame), 2000):
        rows = frame.iloc[offset : offset + 2000][
            ["item_id", "store_id", "date", "units_sold"]
        ].to_dict(orient="records")
        keys = [(row["item_id"], row["store_id"], row["date"]) for row in rows]
        existing = {
            (row.item_id, row.store_id, row.date): row.units_sold
            for row in connection.execute(
                select(table).where(
                    tuple_(table.c.item_id, table.c.store_id, table.c.date).in_(keys)
                )
            )
        }
        new_rows = []
        for key, row in zip(keys, rows, strict=True):
            if key in existing:
                if existing[key] != row["units_sold"]:
                    raise InputError(
                        "correction_not_supported",
                        "Existing sales differ; correction policy pending. Nothing was overwritten",
                        1,
                    )
                unchanged += 1
            else:
                new_rows.append({**row, "load_id": load_id})
        if new_rows:
            connection.execute(insert(table), new_rows)
            inserted += len(new_rows)
    return inserted, unchanged


def ingest(engine: Engine, settings: Settings, selection: Selection) -> LoadResult:
    """One writer; all CORE changes and completion become visible in one transaction."""
    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": INGESTION_LOCK}
        )
        connection.commit()
        if not acquired:
            raise InputError(
                "ingestion_busy", "Another ingestion is running; retry after it finishes"
            )
        try:
            return _ingest_locked(connection, settings, selection)
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": INGESTION_LOCK})
            connection.commit()


def _ingest_locked(connection: Connection, settings: Settings, selection: Selection) -> LoadResult:
    load_id = uuid4()
    table = IngestionLoad.__table__
    sources: list[dict] = []
    processed = inserted = unchanged = 0
    with connection.begin():
        connection.execute(
            update(table)
            .where(table.c.status == "running")
            .values(
                status="failed",
                finished_at=datetime.now(UTC),
                error_code="interrupted",
                error_message="Previous process ended before completing the ingestion",
            )
        )
        connection.execute(
            insert(table).values(
                id=load_id,
                source=settings.source,
                status="running",
                started_at=datetime.now(UTC),
                parser_version=PARSER_VERSION,
                selection=selection.canonical(),
                sources=[{"filename": "sales_train_evaluation.csv"}, {"filename": "calendar.csv"}],
                records_processed=0,
                records_rejected=0,
                records_inserted=0,
                records_unchanged=0,
            )
        )
    logger.info("ingestion_started load_id=%s source=%s", load_id, settings.source)
    try:
        for name in ("sales_train_evaluation.csv", "calendar.csv"):
            sources.append(archive_source(settings.data_dir / name, settings.archive_dir))
            with connection.begin():
                connection.execute(
                    update(table).where(table.c.id == load_id).values(sources=sources)
                )
        identity = fingerprint(settings.source, sources, selection)
        with connection.begin():
            previous = connection.scalar(
                select(table.c.id).where(
                    table.c.fingerprint == identity,
                    table.c.status == "completed",
                    table.c.reused_load_id.is_(None),
                )
            )
            connection.execute(
                update(table).where(table.c.id == load_id).values(fingerprint=identity)
            )
            if previous:
                connection.execute(
                    update(table)
                    .where(table.c.id == load_id)
                    .values(
                        status="completed",
                        finished_at=datetime.now(UTC),
                        reused_load_id=previous,
                    )
                )
        if previous:
            logger.info("ingestion_reused load_id=%s reused_load_id=%s", load_id, previous)
            return LoadResult(load_id, 0, 0, 0, previous)

        sales_path, calendar_path = [
            settings.archive_dir / source["archive_name"] for source in sources
        ]
        calendar = read_calendar(calendar_path, selection)
        with connection.begin():
            for frame in iter_sales(sales_path, calendar, selection):
                processed += len(frame)
                added, matched = _persist_sales(connection, frame, load_id)
                inserted += added
                unchanged += matched
            connection.execute(
                update(table)
                .where(table.c.id == load_id)
                .values(
                    status="completed",
                    finished_at=datetime.now(UTC),
                    records_processed=processed,
                    records_inserted=inserted,
                    records_unchanged=unchanged,
                )
            )
        logger.info(
            "ingestion_completed load_id=%s processed=%d inserted=%d unchanged=%d",
            load_id,
            processed,
            inserted,
            unchanged,
        )
        return LoadResult(load_id, processed, inserted, unchanged)
    except Exception as exc:
        connection.rollback()
        if isinstance(exc, InputError):
            code, message, rejected = exc.code, str(exc), exc.rejected
        elif isinstance(
            exc, (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError, csv.Error)
        ):
            code, message, rejected = "invalid_csv", "Source is not a valid UTF-8 CSV", 0
        elif isinstance(exc, OSError):
            code, message, rejected = (
                "file_access_error",
                "Could not read or archive a source file",
                0,
            )
        else:
            code, message, rejected = (
                "persistence_error",
                "Ingestion failed; transaction rolled back",
                0,
            )
        with connection.begin():
            connection.execute(
                update(table)
                .where(table.c.id == load_id)
                .values(
                    status="failed",
                    finished_at=datetime.now(UTC),
                    error_code=code,
                    error_message=message,
                    records_processed=processed,
                    records_rejected=rejected,
                    records_inserted=0,
                    records_unchanged=0,
                )
            )
        logger.error(
            "ingestion_failed load_id=%s code=%s error_type=%s", load_id, code, type(exc).__name__
        )
        raise IngestionFailed(load_id, code, message) from exc
