from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from demandiq.forecasting.evaluation import metric_values, select_method, summarize
from demandiq.forecasting.features import (
    baseline_forecast,
    recursive_forecast,
    segments,
    training_features,
)
from demandiq.forecasting.protocol import (
    BASELINE,
    CANDIDATE,
    FEATURES,
    MODEL_CONFIG,
    V1,
    ForecastError,
)


@pytest.fixture
def history():
    dates = pd.date_range("2015-01-01", periods=100)
    return pd.DataFrame(
        {"A": np.arange(100), "B": np.arange(100) * 3, "C": np.zeros(100)}, index=dates
    )


def test_protocol_is_exact():
    assert V1.version == "1.0" and V1.horizon == 14
    assert [str(c) for c in V1.cutoffs] == [
        "2016-02-14",
        "2016-02-28",
        "2016-03-13",
        "2016-03-27",
        "2016-04-10",
        "2016-04-24",
    ]
    assert str(V1.test_cutoff) == "2016-05-08"
    windows = V1.manifest()["stages"]
    assert windows[-1]["end"] == "2016-05-22"
    for previous, current in zip(windows, windows[1:], strict=False):
        assert pd.Timestamp(current["start"]) - pd.Timestamp(previous["end"]) == pd.Timedelta(
            1, "D"
        )
    assert MODEL_CONFIG == {
        "loss": "poisson",
        "max_iter": 100,
        "learning_rate": 0.1,
        "max_leaf_nodes": 15,
        "min_samples_leaf": 50,
        "random_state": 42,
        "early_stopping": False,
        "categorical_features": ["item_id"],
    }


def test_all_seven_features_exclude_target_and_preserve_zero(history):
    x, y = training_features(history, history.index[49])
    assert tuple(x.columns) == FEATURES
    row = x[(x.index == history.index[28]) & (x.item_id == "A")].iloc[0]
    assert row.lag_1 == 27 and row.lag_7 == 21 and row.lag_28 == 0
    assert row.rolling_mean_7 == np.mean(np.arange(21, 28))
    assert row.rolling_mean_28 == np.mean(np.arange(28))
    assert row.day_of_week == history.index[28].dayofweek
    assert len(x) == (50 - 28) * 3 and x.index.max() == history.index[49]
    assert x.item_id.cat.categories.tolist() == ["A", "B", "C"]
    assert (x[x.item_id == "C"].iloc[:, :5] == 0).all().all()
    assert y[x.item_id == "A"].iloc[0] == 28
    changed = history.copy()
    changed.loc[history.index[28], "A"] = 10000
    after, _ = training_features(changed, history.index[49])
    pd.testing.assert_series_equal(
        row, after[(after.index == history.index[28]) & (after.item_id == "A")].iloc[0]
    )


def test_future_cannot_change_features_or_segments(history):
    cutoff = history.index[49]
    changed = history.copy()
    changed.loc[changed.index > cutoff, "A"] = 999999
    changed.loc[changed.index > cutoff, "C"] = 888888
    x, y = training_features(history, cutoff)
    future_x, future_y = training_features(changed, cutoff)
    pd.testing.assert_frame_equal(x, future_x)
    pd.testing.assert_series_equal(y, future_y)
    pd.testing.assert_frame_equal(segments(history, cutoff), segments(changed, cutoff))
    assert segments(history, cutoff).loc["C", "volume_segment"] == "low"
    assert segments(history, cutoff).loc["C", "intermittency_segment"] == "high"


def test_baseline_four_known_weekdays_frozen_for_both_weeks(history):
    cutoff = history.index[27]
    forecast = baseline_forecast(history, cutoff)
    for target, row in forecast.iterrows():
        past = history.loc[:cutoff].iloc[-28:]
        expected = past[past.index.dayofweek == target.dayofweek].mean()
        np.testing.assert_array_equal(row.to_numpy(), expected.to_numpy())
    np.testing.assert_array_equal(forecast.iloc[:7].to_numpy(), forecast.iloc[7:].to_numpy())
    assert (forecast.C == 0).all()
    assert forecast.A.iloc[0] % 1 != 0


def test_recursive_steps_use_predictions_not_future_actuals(history):
    class Spy:
        def __init__(self):
            self.inputs = []

        def predict(self, frame):
            self.inputs.append(frame.copy())
            return frame.lag_1.to_numpy() + 0.5

    cutoff = history.index[49]
    model = Spy()
    result = recursive_forecast(model, history, cutoff)
    changed = history.copy()
    changed.loc[changed.index > cutoff] = 1e9
    np.testing.assert_array_equal(result, recursive_forecast(Spy(), changed, cutoff))
    assert model.inputs[1].lag_1.iloc[0] == 49.5
    assert model.inputs[7].lag_7.iloc[0] == 49.5
    assert model.inputs[1].rolling_mean_7.iloc[0] == np.mean([44, 45, 46, 47, 48, 49, 49.5])
    assert model.inputs[1].rolling_mean_28.iloc[0] == np.mean([*range(23, 50), 49.5])
    assert result.A.iloc[-1] == 56
    assert (result.to_numpy() >= 0).all()


@pytest.mark.parametrize("fault", ["short", "missing_day", "missing_value"])
def test_insufficient_history_is_explicit(history, fault):
    if fault == "short":
        history = history.iloc[:27]
    elif fault == "missing_day":
        history = history.drop(history.index[4])
    else:
        history.loc[history.index[4], "A"] = np.nan
    with pytest.raises(ForecastError) as exc:
        baseline_forecast(history, history.index[-1])
    assert exc.value.code == "insufficient_history"


def test_real_candidate_is_deterministic_and_uses_categorical_item(history):
    x, y = training_features(history, history.index[69])
    with threadpool_limits(limits=2):
        first = HistGradientBoostingRegressor(**MODEL_CONFIG).fit(x, y)
        second = HistGradientBoostingRegressor(**MODEL_CONFIG).fit(x, y)
        a = recursive_forecast(first, history, history.index[69])
        b = recursive_forecast(second, history, history.index[69])
    np.testing.assert_array_equal(a, b)
    assert first.n_iter_ == 100 and not first.do_early_stopping_
    assert first.is_categorical_.tolist() == [False] * 6 + [True]


def metric_rows():
    return pd.DataFrame(
        [
            {
                "stage": "fold_1",
                "item_id": item,
                "store_id": "S",
                "method": BASELINE,
                "horizon_step": step,
                "actual_units": 10.0,
                "predicted_units": prediction,
                "volume_segment": "low",
                "intermittency_segment": "high",
            }
            for item, prediction in (("A", 12.0), ("B", 8.0))
            for step in range(1, 15)
        ]
    )


def test_metrics_accumulate_per_sku_without_cancellation():
    m = metric_values(metric_rows())
    assert m["rmse_14"]["value"] == 28
    assert m["wape"]["value"] == 20
    assert m["bias"]["value"] == 0
    assert m["rmse_14"]["denominator"] == 2
    assert m["wape"]["denominator"] == 280
    rows = metric_rows()
    rows.predicted_units += 3
    assert metric_values(rows)["bias"]["value"] == 30


def test_global_rmse_pools_errors_not_fold_scores_or_percentages():
    first = metric_rows()
    second = first.copy()
    second["stage"] = "fold_2"
    second["actual_units"] = 100.0
    second["predicted_units"] = 100.0
    m = metric_values(pd.concat([first, second]))
    assert m["rmse_14"]["value"] == pytest.approx(np.sqrt((28**2 + 28**2) / 4))
    assert m["wape"]["value"] == pytest.approx(100 * 56 / 3080)


def test_zero_denominator_and_horizon_wape():
    rows = metric_rows()
    rows.actual_units = 0.0
    m = metric_values(rows)
    for name in ("wape", "bias"):
        assert m[name] == {
            "value": None,
            "status": "undefined",
            "numerator": 280.0,
            "denominator": 0.0,
        }
    assert m["rmse_14"]["value"] is not None
    metrics = summarize(rows, "fold_1")
    halves = [m for m in metrics if m["scope"] == "horizon"]
    assert {m["scope_value"] for m in halves} == {"1-7", "8-14"}
    assert all(m["value"] is None for m in halves)


def selection_metrics():
    return [
        {"stage": stage, "method": method, "scope": "global", "name": name, "value": score}
        for stage in [*(f"fold_{i}" for i in range(1, 7)), "development"]
        for method, score in ((BASELINE, 10.0), (CANDIDATE, 9.0))
        for name in ("rmse_14", "bias")
    ]


@pytest.mark.parametrize("failure", [None, "rmse_tie", "three_wins", "worse_bias", "undefined"])
def test_exact_selection_rule(failure):
    metrics = deepcopy(selection_metrics())
    for m in metrics:
        if m["method"] != CANDIDATE:
            continue
        if failure == "rmse_tie" and m["stage"] == "development" and m["name"] == "rmse_14":
            m["value"] = 10.0
        if failure == "three_wins" and m["stage"] in ("fold_4", "fold_5", "fold_6"):
            m["value"] = 10.0
        if (
            failure in ("worse_bias", "undefined")
            and m["stage"] == "development"
            and m["name"] == "bias"
        ):
            m["value"] = -11.0 if failure == "worse_bias" else None
    result = select_method(metrics)
    assert result["selected_method"] == (CANDIDATE if failure is None else BASELINE)


def test_test_evidence_is_rejected_by_selection():
    with pytest.raises(ForecastError, match="precede"):
        select_method([*selection_metrics(), {"stage": "test"}])
    with pytest.raises(ForecastError, match="Six folds"):
        select_method([])


def test_twenty_eight_days_are_context_not_training_targets(history):
    train = history.iloc[:28]
    assert len(baseline_forecast(train, train.index[-1])) == 14
    with pytest.raises(ForecastError) as exc:
        training_features(train, train.index[-1])
    assert exc.value.code == "insufficient_training_history"
