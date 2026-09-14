import numpy as np
import pandas as pd

from demandiq.forecasting.protocol import CONTEXT_DAYS, FEATURES, ForecastError


def history_at(data: pd.DataFrame, cutoff) -> pd.DataFrame:
    """Discard the future before any validation, features or segmentation."""
    cutoff = pd.Timestamp(cutoff)
    train = data.loc[data.index <= cutoff].sort_index().sort_index(axis=1).copy()
    if train.index.has_duplicates or train.columns.has_duplicates:
        raise ForecastError("duplicate_observations", "Duplicate dates or product columns")
    if train.empty or len(train) < CONTEXT_DAYS:
        raise ForecastError("insufficient_history", "At least 28 complete days are required")
    expected = pd.date_range(train.index.min(), cutoff, freq="D")
    train = train.reindex(expected)
    missing = train.columns[train.isna().any()].tolist()
    if missing:
        raise ForecastError(
            "insufficient_history", "Missing observations are not zero", {"item_ids": missing}
        )
    values = train.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ForecastError("invalid_sales", "Sales must be finite and nonnegative")
    return train


def training_features(data: pd.DataFrame, cutoff) -> tuple[pd.DataFrame, pd.Series]:
    train = history_at(data, cutoff)
    parts, targets = [], []
    for item, sales in train.items():
        prior = sales.shift(1)
        frame = pd.DataFrame(
            {
                "lag_1": prior,
                "lag_7": sales.shift(7),
                "lag_28": sales.shift(28),
                "rolling_mean_7": prior.rolling(7).mean(),
                "rolling_mean_28": prior.rolling(28).mean(),
                "day_of_week": sales.index.dayofweek,
                "item_id": item,
            }
        ).iloc[CONTEXT_DAYS:]
        parts.append(frame)
        targets.append(sales.iloc[CONTEXT_DAYS:])
    x = pd.concat(parts)
    x["item_id"] = pd.Categorical(x.item_id, categories=train.columns.tolist())
    y = pd.concat(targets).astype(float)
    if x.empty:
        raise ForecastError(
            "insufficient_training_history",
            "One-step training needs targets after the 28-day context",
        )
    return x[list(FEATURES)], y


def next_features(history: pd.DataFrame, target: pd.Timestamp) -> pd.DataFrame:
    values = history.to_numpy(dtype=float)
    return pd.DataFrame(
        {
            "lag_1": values[-1],
            "lag_7": values[-7],
            "lag_28": values[-28],
            "rolling_mean_7": values[-7:].mean(axis=0),
            "rolling_mean_28": values[-28:].mean(axis=0),
            "day_of_week": target.dayofweek,
            "item_id": pd.Categorical(history.columns, categories=history.columns.tolist()),
        }
    )[list(FEATURES)]


def baseline_forecast(data: pd.DataFrame, cutoff, horizon: int = 14) -> pd.DataFrame:
    train = history_at(data, cutoff)
    context = train.iloc[-CONTEXT_DAYS:]
    dates = pd.date_range(pd.Timestamp(cutoff) + pd.Timedelta(days=1), periods=horizon)
    # Exactly four known observations per weekday, frozen at the origin.
    weekday_means = context.groupby(context.index.dayofweek).mean()
    return pd.DataFrame(
        [weekday_means.loc[d.dayofweek].to_numpy() for d in dates],
        index=dates,
        columns=train.columns,
    )


def recursive_forecast(model, data: pd.DataFrame, cutoff, horizon: int = 14) -> pd.DataFrame:
    history = history_at(data, cutoff).iloc[-CONTEXT_DAYS:].astype(float)
    dates = pd.date_range(pd.Timestamp(cutoff) + pd.Timedelta(days=1), periods=horizon)
    predictions = []
    for target in dates:
        prediction = np.asarray(model.predict(next_features(history, target)), dtype=float)
        if prediction.shape != (len(history.columns),) or not np.isfinite(prediction).all():
            raise ForecastError("invalid_predictions", "Model produced invalid predictions")
        if (prediction < 0).any():
            raise ForecastError("invalid_predictions", "Negative forecasts are not allowed")
        predictions.append(prediction)
        history.loc[target] = prediction
    return pd.DataFrame(predictions, index=dates, columns=history.columns)


def segments(data: pd.DataFrame, cutoff) -> pd.DataFrame:
    train = history_at(data, cutoff)
    result = pd.DataFrame(index=train.columns)
    # Equal-sized relative groups, not business thresholds. Stable ties, no activity filter.
    for name, values in (
        ("volume_segment", train.sum()),
        ("intermittency_segment", train.eq(0).mean()),
    ):
        ordered = values.rename("value").rename_axis("item_id").reset_index()
        ordered = ordered.sort_values(["value", "item_id"], kind="stable")
        labels = {}
        for label, indices in zip(
            ("low", "medium", "high"), np.array_split(np.arange(len(ordered)), 3), strict=True
        ):
            labels.update({item: label for item in ordered.iloc[indices].item_id})
        result[name] = [labels[item] for item in result.index]
    return result
