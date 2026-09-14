import numpy as np
import pandas as pd

from demandiq.forecasting.protocol import BASELINE, CANDIDATE, ForecastError


def metric_values(rows: pd.DataFrame) -> dict[str, dict]:
    if rows.empty:
        raise ForecastError("empty_evaluation", "Cannot evaluate an empty selection")
    observed = rows.actual_units.to_numpy(dtype=float)
    predicted = rows.predicted_units.to_numpy(dtype=float)
    if not np.isfinite(observed).all() or not np.isfinite(predicted).all():
        raise ForecastError("invalid_evaluation", "Metrics require finite values")
    error = predicted - observed
    work = rows[["stage", "item_id", "store_id"]].copy()
    work["error"] = error
    totals = work.groupby(["stage", "store_id", "item_id"], observed=True).error.sum()
    denominator = float(observed.sum())
    squared = float(np.square(totals).sum())
    result = {
        "rmse_14": {
            "value": float(np.sqrt(squared / len(totals))),
            "numerator": squared,
            "denominator": float(len(totals)),
            "status": "defined",
        }
    }
    for name, numerator in (("wape", float(np.abs(error).sum())), ("bias", float(error.sum()))):
        result[name] = {
            "value": 100 * numerator / denominator if denominator else None,
            "numerator": numerator,
            "denominator": denominator,
            "status": "defined" if denominator else "undefined",
        }
    return result


def summarize(rows: pd.DataFrame, stage: str) -> list[dict]:
    records = []
    for method, frame in rows.groupby("method", sort=True):
        scopes = [("global", "all", frame)]
        for column, scope in (
            ("volume_segment", "volume"),
            ("intermittency_segment", "intermittency"),
            ("item_id", "sku"),
        ):
            scopes.extend(
                (scope, str(value), group) for value, group in frame.groupby(column, sort=True)
            )
        for scope, value, group in scopes:
            for name, metric in metric_values(group).items():
                records.append(
                    {
                        "stage": stage,
                        "method": method,
                        "scope": scope,
                        "scope_value": value,
                        "name": name,
                        **metric,
                    }
                )
        for first, last in ((1, 7), (8, 14)):
            group = frame[frame.horizon_step.between(first, last)]
            records.append(
                {
                    "stage": stage,
                    "method": method,
                    "scope": "horizon",
                    "scope_value": f"{first}-{last}",
                    "name": "wape",
                    **metric_values(group)["wape"],
                }
            )
    return records


def select_method(metrics: list[dict]) -> dict:
    """Only development evidence is accepted. Test results cannot enter the decision."""
    if any(m["stage"] == "test" for m in metrics):
        raise ForecastError("test_in_selection", "Selection must precede test evaluation")
    values = {
        (m["stage"], m["method"], m["name"]): m["value"] for m in metrics if m["scope"] == "global"
    }
    expected_stages = {f"fold_{i}" for i in range(1, 7)} | {"development"}
    for stage in expected_stages:
        for method in (BASELINE, CANDIDATE):
            for name in ("rmse_14", "bias"):
                if (stage, method, name) not in values:
                    raise ForecastError("incomplete_development", "Six folds are required")
    wins = sum(
        values[(f"fold_{i}", CANDIDATE, "rmse_14")] < values[(f"fold_{i}", BASELINE, "rmse_14")]
        for i in range(1, 7)
    )
    base_bias = values[("development", BASELINE, "bias")]
    candidate_bias = values[("development", CANDIDATE, "bias")]
    checks = {
        "lower_global_rmse": values[("development", CANDIDATE, "rmse_14")]
        < values[("development", BASELINE, "rmse_14")],
        "wins_at_least_four": wins >= 4,
        "absolute_bias_no_worse": base_bias is not None
        and candidate_bias is not None
        and abs(candidate_bias) <= abs(base_bias),
    }
    return {
        "selected_method": CANDIDATE if all(checks.values()) else BASELINE,
        "checks": checks,
        "fold_wins": wins,
        "baseline": {k: values[("development", BASELINE, k)] for k in ("rmse_14", "bias")},
        "candidate": {k: values[("development", CANDIDATE, k)] for k in ("rmse_14", "bias")},
        "rule": "lower pooled RMSE14 AND wins >= 4/6 AND abs bias no worse; ties baseline",
    }
