import csv
import hashlib
import json
import pickle
from dataclasses import replace
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select, text
from threadpoolctl import threadpool_limits

from demandiq.db import ForecastMetric, ForecastPrediction, ForecastRun
from demandiq.forecasting import service
from demandiq.forecasting.features import recursive_forecast
from demandiq.forecasting.protocol import CANDIDATE, V1, ForecastError
from demandiq.forecasting.report import generate_report
from demandiq.ingestion.m5 import META_COLUMNS, Selection
from demandiq.ingestion.service import ingest

pytestmark = pytest.mark.integration


@pytest.fixture
def forecast_data(db, settings):
    protocol = replace(
        V1,
        source="synthetic-control",
        store_id="DEMO_STORE",
        department_id="DEMO_DEPT",
        expected_skus=3,
    )
    dates = pd.date_range(protocol.start, protocol.end)
    days = [f"d_{i + 1}" for i in range(len(dates))]
    with (settings.data_dir / "calendar.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["d", "date"])
        writer.writerows(zip(days, dates.strftime("%Y-%m-%d"), strict=True))
    arrays = [
        1 + np.arange(len(dates)) % 7,
        np.where(np.arange(len(dates)) % 5 == 0, 5, 0),
        np.zeros(len(dates), dtype=int),
    ]
    with (settings.data_dir / "sales_train_evaluation.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(META_COLUMNS + days)
        for item, values in zip(("A", "B", "C"), arrays, strict=True):
            writer.writerow(
                [item, "DEMO_STORE", "DEMO_DEPT", "DEMO_CAT", "DEMO_STATE", *map(int, values)]
            )
    ingest(
        db,
        settings,
        Selection(store_ids=["DEMO_STORE"], start_date=protocol.start, end_date=protocol.end),
    )
    return protocol


def test_small_e2e_persistence_selection_order_artifact_and_report(
    db, forecast_data, tmp_path, monkeypatch
):
    original = service.evaluate_stage
    checked_test = []

    def observed_stage(data, stage, cutoff, protocol, directory):
        if stage == "test":
            with db.connect() as connection:
                r = connection.execute(select(ForecastRun.__table__)).mappings().one()
                assert r["selected_method"] and r["selected_at"] < datetime.now(UTC)
                assert r["status"] == "running"
                assert (
                    connection.scalar(
                        select(func.count())
                        .select_from(ForecastMetric)
                        .where(ForecastMetric.stage == "test")
                    )
                    == 0
                )
                checked_test.append(r["selected_method"])
        return original(data, stage, cutoff, protocol, directory)

    monkeypatch.setattr(service, "evaluate_stage", observed_stage)
    run_id = service.run_backtest(db, tmp_path, forecast_data)
    with db.connect() as conn:
        run = conn.execute(select(ForecastRun.__table__)).mappings().one()
        assert run["id"] == run_id and run["status"] == "completed"
        assert run["selected_method"] == checked_test[0]
        assert len(run["source_loads"]) == 1 and len(run["data_fingerprint"]) == 64
        assert len(run["stages"]) == 7
        assert conn.scalar(select(func.count()).select_from(ForecastPrediction)) == 3 * 14 * 2 * 7
        assert (
            conn.scalar(
                select(func.count())
                .select_from(ForecastMetric)
                .where(ForecastMetric.status == "undefined")
            )
            > 0
        )
        predictions = pd.read_sql(
            select(ForecastPrediction.__table__).where(
                ForecastPrediction.stage == "fold_1", ForecastPrediction.method == CANDIDATE
            ),
            conn,
        )
    artifact = run["stages"][0]["artifact"]
    from pathlib import Path

    payload = Path(artifact["path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    saved = pickle.loads(payload)
    data, _ = service.read_sales(db, forecast_data)
    with threadpool_limits(limits=2):
        restored = recursive_forecast(saved["model"], data, forecast_data.cutoffs[0])
    for row in predictions.itertuples():
        assert restored.loc[pd.Timestamp(row.target_date), row.item_id] == row.predicted_units
    path = generate_report(db, run_id, tmp_path)
    before = path.read_bytes()
    assert generate_report(db, run_id, tmp_path).read_bytes() == before
    results = json.loads((path.parent / "results.json").read_text())
    assert results["run"]["selected_method"] == checked_test[0]
    assert "weekday_mean_4" in path.read_text()

    # A new failed attempt must leave the completed run and its output intact.
    def fail(data, stage, cutoff, protocol, directory):
        if stage == "test":
            raise ForecastError("controlled_failure", "Deliberate test-stage failure")
        return original(data, stage, cutoff, protocol, directory)

    monkeypatch.setattr(service, "evaluate_stage", fail)
    with pytest.raises(service.ForecastFailed) as exc:
        service.run_backtest(db, tmp_path, forecast_data)
    with db.connect() as conn:
        assert (
            conn.scalar(select(ForecastRun.status).where(ForecastRun.id == run_id)) == "completed"
        )
        failed = (
            conn.execute(select(ForecastRun.__table__).where(ForecastRun.id == exc.value.run_id))
            .mappings()
            .one()
        )
        assert failed["status"] == "failed" and failed["error_code"] == "controlled_failure"
        assert failed["selected_method"] == run["selected_method"]
        assert len(failed["stages"]) == 6
        assert (
            conn.scalar(
                select(func.count())
                .select_from(ForecastPrediction)
                .where(
                    ForecastPrediction.run_id == exc.value.run_id,
                    ForecastPrediction.stage == "test",
                )
            )
            == 0
        )
    with pytest.raises(ForecastError, match="completed"):
        generate_report(db, exc.value.run_id, tmp_path)
    assert path.read_bytes() == before


def test_incomplete_data_creates_failed_run_without_excluding_sku(db, forecast_data, tmp_path):
    with db.begin() as conn:
        conn.execute(text("DELETE FROM core.sales WHERE item_id='C' AND date='2015-01-02'"))
    with pytest.raises(service.ForecastFailed) as exc:
        service.run_backtest(db, tmp_path, forecast_data)
    assert exc.value.code == "insufficient_history"
    with db.connect() as conn:
        assert conn.scalar(select(ForecastRun.status)) == "failed"
        assert conn.scalar(select(func.count()).select_from(ForecastPrediction)) == 0


def test_forecast_lock_prevents_parallel_writer(db, tmp_path):
    with db.connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": service.FORECAST_LOCK})
        lock.commit()
        try:
            with pytest.raises(ForecastError, match="already running"):
                service.run_backtest(db, tmp_path)
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": service.FORECAST_LOCK})
            lock.commit()
