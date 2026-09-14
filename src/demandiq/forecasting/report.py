import json
from pathlib import Path
from uuid import UUID

import pandas as pd
from sqlalchemy import select

from demandiq.db import ForecastMetric, ForecastPrediction, ForecastRun
from demandiq.forecasting.protocol import BASELINE, CANDIDATE, ForecastError


def generate_report(engine, run_id: UUID, artifacts_dir: Path) -> Path:
    with engine.connect() as connection:
        row = (
            connection.execute(select(ForecastRun.__table__).where(ForecastRun.id == run_id))
            .mappings()
            .first()
        )
        if row is None or row["status"] != "completed":
            raise ForecastError("run_not_completed", "Reports require an explicitly completed run")
        run = dict(row)
        metrics = [
            dict(r)
            for r in connection.execute(
                select(ForecastMetric.__table__).where(ForecastMetric.run_id == run_id)
            ).mappings()
        ]
        predictions = pd.read_sql(
            select(ForecastPrediction.__table__).where(ForecastPrediction.run_id == run_id),
            connection,
        )
    metrics.sort(key=lambda m: (m["stage"], m["scope"], m["scope_value"], m["method"], m["name"]))
    directory = artifacts_dir / str(run_id)
    directory.mkdir(parents=True, exist_ok=True)
    evidence = {"run": run, "metrics": metrics}
    (directory / "results.json").write_text(
        json.dumps(evidence, default=str, indent=2, allow_nan=False), encoding="utf-8"
    )
    predictions.sort_values(["stage", "method", "item_id", "target_date"]).to_csv(
        directory / "forecasts.csv", index=False
    )
    values = {
        (m["stage"], m["method"], m["scope"], m["scope_value"], m["name"]): m["value"]
        for m in metrics
    }

    def value(stage, method, name, scope="global", group="all"):
        v = values[(stage, method, scope, group, name)]
        return "undefined (denominator=0)" if v is None else f"{v:.6f}"

    lines = [
        "# DemandIQ - Forecasting V1 experiment",
        "",
        f"Protocol version: {run['protocol_version']}  ",
        f"Run: {run_id}  ",
        f"Status: {run['status']}  ",
        f"Source: {run['source']}  ",
        f"Selection: {json.dumps(run['selection'])}  ",
        f"Data fingerprint: {run['data_fingerprint']}  ",
        f"Data summary: {json.dumps(run['configuration']['data_summary'])}  ",
        f"Random state: {run['random_state']}  ",
        f"Total experiment seconds (report export excluded): {run['duration_seconds']:.3f}  ",
        f"Peak Python RSS MiB (Linux process lifetime): {run['configuration']['peak_rss_mib']}",
        "",
        "## Temporal protocol and performance",
        "",
        "| Stage | Cutoff | Train days | Features s | Fit s | Predict s | Total s | Model bytes |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in run["stages"]:
        lines.append(
            f"| {s['stage']} | {s['cutoff']} | {s['training_days']} | "
            f"{s['feature_seconds']:.3f} | {s['fit_seconds']:.3f} | "
            f"{s['prediction_seconds']:.3f} | {s['duration_seconds']:.3f} | "
            f"{s['artifact']['size_bytes']} |"
        )
    lines += [
        "",
        "## Baseline and candidate",
        "",
        "RMSE14 is pooled across SKU/origin cumulative errors, never across store totals.",
        "WAPE and Bias are percentages; positive Bias means overprediction.",
        "",
        "| Stage | Method | RMSE14 | WAPE daily % | Bias % | WAPE 1-7 % | WAPE 8-14 % |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for stage in [*(f"fold_{i}" for i in range(1, 7)), "development", "test"]:
        for method in (BASELINE, CANDIDATE):
            lines.append(
                f"| {stage} | {method} | {value(stage, method, 'rmse_14')} | "
                f"{value(stage, method, 'wape')} | {value(stage, method, 'bias')} | "
                f"{value(stage, method, 'wape', 'horizon', '1-7')} | "
                f"{value(stage, method, 'wape', 'horizon', '8-14')} |"
            )
    lines += [
        "",
        "## Frozen selection",
        "",
        f"Selected method: **{run['selected_method']}**",
        f"Decision committed at: {run['selected_at']}",
        "",
        "Decision uses development only:",
        "",
        "```json",
        json.dumps(run["decision"], indent=2),
        "```",
    ]
    selected = run["selected_method"]
    other = BASELINE if selected == CANDIDATE else CANDIDATE
    selected_score = values[("test", selected, "global", "all", "rmse_14")]
    other_score = values[("test", other, "global", "all", "rmse_14")]
    lines += [
        "",
        f"Test RMSE14 of selected method: {selected_score:.6f}; other: {other_score:.6f}.",
        f"Selected method loses in test: **{selected_score > other_score}**.",
        "The test result does not alter the frozen selection.",
        "",
        "## Segments",
        "",
        "Equal-count training-only tertiles; stable item_id tie-break. Intermittency high "
        "means more zero days. Membership may change between folds.",
        "",
        "| Stage | Segment | Group | Method | RMSE14 | WAPE % | Bias % |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for stage in ("development", "test"):
        for scope in ("volume", "intermittency"):
            groups = sorted(
                {m["scope_value"] for m in metrics if m["stage"] == stage and m["scope"] == scope}
            )
            for group in groups:
                for method in (BASELINE, CANDIDATE):
                    lines.append(
                        f"| {stage} | {scope} | {group} | {method} | "
                        f"{value(stage, method, 'rmse_14', scope, group)} | "
                        f"{value(stage, method, 'wape', scope, group)} | "
                        f"{value(stage, method, 'bias', scope, group)} |"
                    )
    undefined = sum(m["status"] == "undefined" for m in metrics)
    lines += [
        "",
        "## Artifacts and reproducibility",
        "",
        "results.json includes all per-SKU/per-fold metrics, denominators, source loads, "
        "versions, timing, feature schema, full estimator parameters and model checksums.",
        "forecasts.csv contains every persisted prediction, observed target and fold segment.",
        "Model pickle files are local generated artifacts; load only trusted, checksum-verified "
        "files with matching dependency versions.",
        "",
        "## Problems and limitations",
        "",
        f"Recorded run error: {run['error_code']}. Undefined metric entries: {undefined}.",
        "Undefined percentages retain a zero denominator and null value; no epsilon is used.",
        "Observed sales are not unconstrained demand. Zeros do not identify stockouts.",
        "Level shifts, intermittency and recursive error accumulation limit reliability.",
        "Six folds and one 14-day test do not establish annual or cross-store performance.",
        "Descriptive analysis previously examined the full dataset; this is not a never-seen test.",
        "No tuning, price, events, SNAP, replenishment or inventory optimization is performed.",
        "No future production forecast beyond the evaluated test is generated by this command.",
    ]
    path = directory / "forecasting-v1-report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
