import csv
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, text

from alembic import command
from demandiq.api.app import create_app
from demandiq.db import IngestionLoad, Product, Sale
from demandiq.ingestion.m5 import InputError
from demandiq.ingestion.service import INGESTION_LOCK, IngestionFailed, ingest

pytestmark = pytest.mark.integration


def sales_count(db):
    with db.connect() as connection:
        return connection.scalar(select(func.count()).select_from(Sale))


def test_end_to_end_reingestion_and_api(db, settings, selection):
    original = ingest(db, settings, selection)
    repeated = ingest(db, settings, selection)
    assert original.records_inserted == 6
    assert repeated.reused_load_id == original.load_id
    assert repeated.load_id != original.load_id
    assert sales_count(db) == 6
    with TestClient(create_app(settings, db)) as client:
        assert client.get("/api/v1/ready").status_code == 200
        params = {
            "item_id": "DEMO_ITEM_A",
            "store_id": "DEMO_STORE",
            "start_date": "2020-01-01",
            "end_date": "2020-01-03",
        }
        response = client.get("/api/v1/sales", params=params)
        assert response.status_code == 200
        assert [row["units_sold"] for row in response.json()["items"]] == [2, 0, 4]
        assert {row["load_id"] for row in response.json()["items"]} == {str(original.load_id)}
        assert response.json()["next_after_date"] is None
        trace = client.get(f"/api/v1/loads/{original.load_id}").json()
        assert trace["status"] == "completed"
        assert trace["source"] == "synthetic-control"
        assert trace["records_processed"] == 6
        assert len(trace["sources"][0]["sha256"]) == 64
        assert "archive_name" not in trace["sources"][0]
        assert len(client.get("/api/v1/loads").json()["items"]) == 2
        assert client.get(f"/api/v1/loads/{uuid4()}").status_code == 404
        page = client.get("/api/v1/sales", params={**params, "limit": 2}).json()
        assert page["next_after_date"] == "2020-01-02"
        second = client.get(
            "/api/v1/sales", params={**params, "after_date": page["next_after_date"]}
        ).json()
        assert [row["units_sold"] for row in second["items"]] == [4]
        assert (
            client.get("/api/v1/sales", params={**params, "item_id": "UNKNOWN"}).json()["items"]
            == []
        )
        assert (
            client.get("/api/v1/sales", params={**params, "end_date": "2019-01-01"}).status_code
            == 422
        )
        assert client.get("/api/v1/sales", params={**params, "limit": 0}).status_code == 422


def test_overlapping_selection_retains_original_provenance(db, settings, selection):
    first = ingest(db, settings, selection.model_copy(update={"end_date": date(2020, 1, 2)}))
    second = ingest(db, settings, selection)
    assert first.records_inserted == 4
    assert second.records_inserted == 2
    assert second.records_unchanged == 4
    assert sales_count(db) == 6
    with db.connect() as connection:
        assert (
            connection.scalar(select(Sale.load_id).where(Sale.date == date(2020, 1, 1)).limit(1))
            == first.load_id
        )


def test_correction_fails_without_overwriting(db, settings, selection):
    first = ingest(db, settings, selection)
    path = settings.data_dir / "sales_train_evaluation.csv"
    path.write_text(path.read_text().replace(",2,0,4", ",9,0,4"))
    with pytest.raises(IngestionFailed) as error:
        ingest(db, settings, selection)
    assert error.value.code == "correction_not_supported"
    with db.connect() as connection:
        load = (
            connection.execute(
                select(IngestionLoad.__table__).where(IngestionLoad.id == error.value.load_id)
            )
            .mappings()
            .one()
        )
        assert load["status"] == "failed"
        assert load["records_inserted"] == 0
        assert load["records_rejected"] == 1
        assert (
            connection.scalar(
                select(Sale.units_sold).where(
                    Sale.item_id == "DEMO_ITEM_A", Sale.date == date(2020, 1, 1)
                )
            )
            == 2
        )
        assert (
            connection.scalar(select(IngestionLoad.status).where(IngestionLoad.id == first.load_id))
            == "completed"
        )


def test_late_failure_rolls_back_earlier_batches(db, settings, selection):
    path = settings.data_dir / "sales_train_evaluation.csv"
    rows = list(csv.reader(path.open()))
    sample = rows[1]
    many = [[f"ITEM_{i}", *sample[1:]] for i in range(129)]
    with path.open("w", newline="") as handle:
        csv.writer(handle).writerows([rows[0], *many, many[0]])
    with pytest.raises(IngestionFailed) as error:
        ingest(db, settings, selection)
    assert error.value.code == "duplicate_series"
    assert sales_count(db) == 0
    with db.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(Product)) == 0
        assert connection.scalar(select(IngestionLoad.records_processed)) > 0


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("missing", "missing_file"),
        ("columns", "missing_columns"),
        ("blank", "invalid_units"),
        ("date", "invalid_calendar"),
    ],
)
def test_failures_are_traced_and_retryable(db, settings, selection, fault, expected):
    path = settings.data_dir / ("calendar.csv" if fault == "date" else "sales_train_evaluation.csv")
    original = path.read_bytes()
    if fault == "missing":
        path.unlink()
    elif fault == "columns":
        path.write_text(original.decode().replace("item_id", "wrong_id"))
    elif fault == "blank":
        path.write_text(original.decode().replace(",2,0,4", ",2,,4"))
    else:
        path.write_text(original.decode().replace("2020-01-01", "2020-02-31"))
    with pytest.raises(IngestionFailed) as error:
        ingest(db, settings, selection)
    assert error.value.code == expected
    assert sales_count(db) == 0
    with TestClient(create_app(settings, db)) as client:
        result = client.get(f"/api/v1/loads/{error.value.load_id}").json()
        assert result["status"] == "failed"
        assert result["error_code"] == expected
    path.write_bytes(original)
    assert ingest(db, settings, selection).records_inserted == 6


def test_writer_lock_prevents_concurrent_ingestion(db, settings, selection):
    with db.connect() as owner:
        owner.execute(text("SELECT pg_advisory_lock(:key)"), {"key": INGESTION_LOCK})
        owner.commit()
        try:
            with pytest.raises(InputError, match="Another ingestion"):
                ingest(db, settings, selection)
        finally:
            owner.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": INGESTION_LOCK})
            owner.commit()
    assert sales_count(db) == 0


def test_interrupted_attempt_is_recovered(db, settings, selection):
    abandoned = uuid4()
    with db.begin() as connection:
        connection.execute(
            insert(IngestionLoad).values(
                id=abandoned,
                source="synthetic-control",
                status="running",
                started_at=datetime.now(UTC),
                parser_version="m5-sales-v1",
                selection=selection.canonical(),
                sources=[],
                records_processed=0,
                records_rejected=0,
                records_inserted=0,
                records_unchanged=0,
            )
        )
    ingest(db, settings, selection)
    with db.connect() as connection:
        assert (
            connection.scalar(select(IngestionLoad.error_code).where(IngestionLoad.id == abandoned))
            == "interrupted"
        )


def test_migrations_match_metadata_and_round_trip(db):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with db.begin() as connection:
        config.attributes["connection"] = connection
        command.check(config)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    assert sales_count(db) == 0
