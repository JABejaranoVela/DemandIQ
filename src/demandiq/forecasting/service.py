import hashlib
import importlib.metadata
import json
import logging
import pickle
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sqlalchemy import Engine, insert, select, text, update
from threadpoolctl import threadpool_limits

from demandiq.db import ForecastMetric, ForecastPrediction, ForecastRun, IngestionLoad
from demandiq.forecasting.evaluation import select_method, summarize
from demandiq.forecasting.features import (
    baseline_forecast,
    history_at,
    recursive_forecast,
    segments,
    training_features,
)
from demandiq.forecasting.protocol import (
    BASELINE,
    CANDIDATE,
    CPU_THREADS,
    FEATURES_VERSION,
    MODEL_CONFIG,
    V1,
    ForecastError,
    Protocol,
)

logger = logging.getLogger(__name__)
FORECAST_LOCK = 481901338


def jsonable(value):
    return json.loads(json.dumps(value, default=str, allow_nan=False))


def runtime_versions() -> dict:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    versions = {
        p: importlib.metadata.version(p)
        for p in ("scikit-learn", "numpy", "pandas", "scipy", "threadpoolctl", "sqlalchemy")
    }
    versions.update(
        python=platform.python_version(),
        platform=platform.platform(),
        source_sha256=digest.hexdigest(),
    )
    lock = Path("uv.lock")
    versions["uv_lock_sha256"] = (
        hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None
    )
    return versions


def read_sales(engine: Engine, protocol: Protocol) -> tuple[pd.DataFrame, dict]:
    query = text(
        "SELECT s.item_id,s.store_id,s.date,s.units_sold,s.load_id "
        "FROM core.sales s JOIN core.products p USING(item_id) "
        "JOIN raw.ingestion_loads l ON l.id=s.load_id "
        "WHERE s.store_id=:store AND p.department_id=:department "
        "AND l.source=:source AND l.status='completed' "
        "AND s.date BETWEEN :start AND :end ORDER BY s.date,s.item_id"
    )
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        data = pd.read_sql(
            query,
            connection,
            params={
                "store": protocol.store_id,
                "department": protocol.department_id,
                "source": protocol.source,
                "start": protocol.start,
                "end": protocol.end,
            },
        )
        ids = data.load_id.unique().tolist()
        source_rows = (
            connection.execute(select(IngestionLoad.__table__).where(IngestionLoad.id.in_(ids)))
            .mappings()
            .all()
        )
    if data.empty:
        raise ForecastError("insufficient_history", "No completed sales for this selection")
    if data.duplicated(["item_id", "store_id", "date"]).any():
        raise ForecastError("duplicate_observations", "Duplicate logical sales keys")
    if data.item_id.nunique() != protocol.expected_skus:
        raise ForecastError(
            "unexpected_skus",
            "The frozen selection is incomplete",
            {"expected": protocol.expected_skus, "actual": data.item_id.nunique()},
        )
    values = data.units_sold.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values % 1 != 0).any():
        raise ForecastError("invalid_sales", "Observed sales must be nonnegative integers")
    identity = data[["item_id", "store_id", "date", "units_sold"]].to_csv(index=False).encode()
    provenance = {
        "fingerprint": hashlib.sha256(identity).hexdigest(),
        "loads": jsonable(
            [
                {
                    "load_id": r["id"],
                    "fingerprint": r["fingerprint"],
                    "parser_version": r["parser_version"],
                    "sources": r["sources"],
                }
                for r in sorted(source_rows, key=lambda x: str(x["id"]))
            ]
        ),
        "observations": len(data),
        "total_units": int(data.units_sold.sum()),
        "zero_observations": int(data.units_sold.eq(0).sum()),
    }
    data["date"] = pd.to_datetime(data.date)
    wide = data.pivot(index="date", columns="item_id", values="units_sold")
    wide = wide.reindex(pd.date_range(protocol.start, protocol.end)).sort_index(axis=1)
    if wide.isna().any().any():
        raise ForecastError(
            "insufficient_history",
            "Incomplete daily grid; missing is not zero",
            {"item_ids": wide.columns[wide.isna().any()].tolist()},
        )
    return wide, provenance


def evaluate_stage(data: pd.DataFrame, stage: str, cutoff, protocol: Protocol, directory: Path):
    began = time.perf_counter()
    started_at = datetime.now(UTC)
    train = history_at(data, cutoff)
    tick = time.perf_counter()
    x, y = training_features(train, cutoff)
    feature_seconds = time.perf_counter() - tick
    if y.sum() <= 0:
        raise ForecastError("candidate_not_trainable", "Poisson training requires positive total")
    tick = time.perf_counter()
    model = HistGradientBoostingRegressor(**MODEL_CONFIG)
    model.fit(x, y)
    fit_seconds = time.perf_counter() - tick
    tick = time.perf_counter()
    forecasts = {
        BASELINE: baseline_forecast(train, cutoff, protocol.horizon),
        CANDIDATE: recursive_forecast(model, train, cutoff, protocol.horizon),
    }
    prediction_seconds = time.perf_counter() - tick
    membership = segments(train, cutoff)
    # Target observations are accessed only after both full forecasts exist.
    dates = forecasts[BASELINE].index
    truth = data.reindex(dates)[train.columns]
    if truth.isna().any().any():
        raise ForecastError("missing_evaluation_targets", "Observed horizon is incomplete")
    records = []
    for method, forecast in forecasts.items():
        for step, target in enumerate(dates, 1):
            for item in train.columns:
                records.append(
                    {
                        "stage": stage,
                        "method": method,
                        "store_id": protocol.store_id,
                        "item_id": item,
                        "cutoff": pd.Timestamp(cutoff).date(),
                        "target_date": target.date(),
                        "horizon_step": step,
                        "predicted_units": float(forecast.loc[target, item]),
                        "actual_units": float(truth.loc[target, item]),
                        **membership.loc[item].to_dict(),
                    }
                )
    frame = pd.DataFrame(records)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stage}-candidate.pkl"
    # Local generated artifacts only. Nothing from users is deserialized by this batch.
    payload = pickle.dumps(
        {
            "model": model,
            "items": train.columns.tolist(),
            "protocol": jsonable(protocol.manifest()),
            "cutoff": str(cutoff),
        },
        protocol=pickle.HIGHEST_PROTOCOL,
    )
    with path.open("xb") as handle:
        handle.write(payload)
    metrics = summarize(frame, stage)
    details = {
        "stage": stage,
        "cutoff": str(cutoff),
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "train_start": str(train.index.min().date()),
        "training_days": len(train),
        "training_rows": len(x),
        "feature_seconds": feature_seconds,
        "fit_seconds": fit_seconds,
        "prediction_seconds": prediction_seconds,
        "duration_seconds": time.perf_counter() - began,
        "model_parameters": jsonable(model.get_params()),
        "artifact": {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        },
        "segment_counts": {
            name: membership[name].value_counts().to_dict() for name in membership.columns
        },
    }
    return frame, metrics, details


class ForecastFailed(ForecastError):
    def __init__(self, run_id: UUID, code: str, message: str):
        super().__init__(code, message)
        self.run_id = run_id


def run_backtest(engine: Engine, artifacts_dir: Path, protocol: Protocol = V1) -> UUID:
    with engine.connect() as lock:
        acquired = lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": FORECAST_LOCK})
        lock.commit()
        if not acquired:
            raise ForecastError("forecast_busy", "A forecasting execution is already running")
        try:
            with engine.begin() as connection:
                connection.execute(
                    update(ForecastRun)
                    .where(ForecastRun.status == "running")
                    .values(
                        status="failed",
                        finished_at=datetime.now(UTC),
                        error_code="interrupted",
                        error_message="Previous forecasting process ended before completion",
                    )
                )
            with threadpool_limits(limits=CPU_THREADS):
                return _run_locked(engine, artifacts_dir, protocol)
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": FORECAST_LOCK})
            lock.commit()


def _run_locked(engine: Engine, artifacts_dir: Path, protocol: Protocol) -> UUID:
    run_id = uuid4()
    began = time.perf_counter()
    configuration = jsonable(protocol.manifest())
    with engine.begin() as connection:
        connection.execute(
            insert(ForecastRun).values(
                id=run_id,
                kind="backtest",
                status="running",
                started_at=datetime.now(UTC),
                source=protocol.source,
                source_loads=[],
                selection={
                    "store_id": protocol.store_id,
                    "department_id": protocol.department_id,
                    "start_date": str(protocol.start),
                    "end_date": str(protocol.end),
                    "expected_skus": protocol.expected_skus,
                },
                train_start=protocol.start,
                train_end=protocol.test_cutoff,
                cutoff=protocol.test_cutoff,
                horizon=protocol.horizon,
                protocol_version=protocol.version,
                features_version=FEATURES_VERSION,
                method="baseline_and_candidate",
                configuration=configuration,
                random_state=MODEL_CONFIG["random_state"],
                versions=runtime_versions(),
                stages=[],
            )
        )
    logger.info("forecast_started run_id=%s protocol=%s", run_id, protocol.version)
    directory = artifacts_dir / str(run_id)
    stages = []
    try:
        tick = time.perf_counter()
        data, provenance = read_sales(engine, protocol)
        configuration["data_summary"] = {
            k: v for k, v in provenance.items() if k not in ("loads", "fingerprint")
        }
        configuration["read_seconds"] = time.perf_counter() - tick
        with engine.begin() as connection:
            connection.execute(
                update(ForecastRun)
                .where(ForecastRun.id == run_id)
                .values(
                    data_fingerprint=provenance["fingerprint"],
                    source_loads=provenance["loads"],
                    configuration=configuration,
                )
            )
        dev_frames, dev_metrics = [], []
        for stage, cutoff in protocol.stages():
            if stage == "test":
                # Freeze and COMMIT the decision before the test is trained or evaluated.
                pooled = summarize(pd.concat(dev_frames, ignore_index=True), "development")
                dev_metrics.extend(pooled)
                decision = select_method(dev_metrics)
                with engine.begin() as connection:
                    connection.execute(
                        insert(ForecastMetric), [{"run_id": run_id, **m} for m in pooled]
                    )
                    connection.execute(
                        update(ForecastRun)
                        .where(ForecastRun.id == run_id)
                        .values(
                            selected_method=decision["selected_method"],
                            decision=decision,
                            selected_at=datetime.now(UTC),
                        )
                    )
                logger.info(
                    "forecast_selection_frozen run_id=%s method=%s checks=%s",
                    run_id,
                    decision["selected_method"],
                    decision["checks"],
                )
            logger.info(
                "forecast_stage_started run_id=%s stage=%s cutoff=%s", run_id, stage, cutoff
            )
            frame, metrics, details = evaluate_stage(data, stage, cutoff, protocol, directory)
            stages.append(details)
            with engine.begin() as connection:
                rows = frame.to_dict(orient="records")
                for offset in range(0, len(rows), 2000):
                    connection.execute(
                        insert(ForecastPrediction),
                        [{"run_id": run_id, **r} for r in rows[offset : offset + 2000]],
                    )
                connection.execute(
                    insert(ForecastMetric), [{"run_id": run_id, **m} for m in metrics]
                )
                connection.execute(
                    update(ForecastRun)
                    .where(ForecastRun.id == run_id)
                    .values(stages=jsonable(stages))
                )
            if stage != "test":
                dev_frames.append(frame)
                dev_metrics.extend(metrics)
            logger.info(
                "forecast_stage_completed run_id=%s stage=%s seconds=%.3f",
                run_id,
                stage,
                details["duration_seconds"],
            )
        try:
            import resource

            # Linux ru_maxrss is KiB. This is a process lifetime peak, not DB/host memory.
            configuration["peak_rss_mib"] = (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            )
        except ImportError:
            configuration["peak_rss_mib"] = None
        with engine.begin() as connection:
            connection.execute(
                update(ForecastRun)
                .where(ForecastRun.id == run_id)
                .values(
                    status="completed",
                    finished_at=datetime.now(UTC),
                    duration_seconds=time.perf_counter() - began,
                    configuration=configuration,
                )
            )
        logger.info(
            "forecast_completed run_id=%s seconds=%.3f", run_id, time.perf_counter() - began
        )
        return run_id
    except Exception as exc:
        code = exc.code if isinstance(exc, ForecastError) else "forecast_execution_error"
        message = str(exc) if isinstance(exc, ForecastError) else "Execution failed; inspect stage"
        details = (
            exc.details if isinstance(exc, ForecastError) else {"error_type": type(exc).__name__}
        )
        with engine.begin() as connection:
            connection.execute(
                update(ForecastRun)
                .where(ForecastRun.id == run_id)
                .values(
                    status="failed",
                    finished_at=datetime.now(UTC),
                    duration_seconds=time.perf_counter() - began,
                    error_code=code,
                    error_message=message,
                    error_details=jsonable(details),
                )
            )
        logger.error(
            "forecast_failed run_id=%s code=%s error_type=%s", run_id, code, type(exc).__name__
        )
        raise ForecastFailed(run_id, code, message) from exc
