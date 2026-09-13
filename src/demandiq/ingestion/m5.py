import csv
import hashlib
import json
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PARSER_VERSION = "m5-sales-v1"
ID_PATTERN = r"^[A-Za-z0-9_]{1,100}$"
Identifier = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
META_COLUMNS = ["item_id", "store_id", "dept_id", "cat_id", "state_id"]


class InputError(Exception):
    def __init__(self, code: str, message: str, rejected: int = 0):
        super().__init__(message)
        self.code = code
        self.rejected = rejected


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    store_ids: list[Identifier] = Field(min_length=1)
    item_ids: list[Identifier] = Field(default_factory=list)
    department_ids: list[Identifier] = Field(default_factory=list)
    category_ids: list[Identifier] = Field(default_factory=list)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_range(self) -> "Selection":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    def canonical(self) -> dict:
        result = self.model_dump(mode="json")
        for key in ("store_ids", "item_ids", "department_ids", "category_ids"):
            result[key] = sorted(set(result[key]))
        return result


def fingerprint(source: str, sources: list[dict], selection: Selection) -> str:
    payload = {
        "source": source,
        "parser_version": PARSER_VERSION,
        "selection": selection.canonical(),
        "files": sorted((s["filename"], s["sha256"]) for s in sources),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def check_header(path: Path, required: list[str]) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), [])
    if len(header) != len(set(header)):
        raise InputError("duplicate_columns", f"Duplicate columns in {path.name}")
    if not set(required).issubset(header):
        raise InputError("missing_columns", f"Required columns absent in {path.name}")


def read_calendar(path: Path, selection: Selection) -> dict[str, date]:
    check_header(path, ["d", "date"])
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=["d", "date"])
    if frame["d"].duplicated().any() or frame["date"].duplicated().any():
        raise InputError("duplicate_calendar", "Calendar dates and day identifiers must be unique")
    valid_days = frame["d"].str.fullmatch(r"d_[1-9][0-9]*")
    valid_dates = frame["date"].str.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
    if not valid_days.all() or not valid_dates.all():
        raise InputError("invalid_calendar", "Calendar contains invalid day identifiers or dates")
    try:
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise").dt.date
    except (ValueError, OverflowError) as exc:
        raise InputError("invalid_calendar", "Calendar contains invalid dates") from exc
    chosen = frame.loc[frame["date"].between(selection.start_date, selection.end_date)]
    expected = (selection.end_date - selection.start_date).days + 1
    if len(chosen) != expected:
        raise InputError("missing_dates", "Calendar does not cover the entire requested date range")
    return dict(chosen.sort_values("date")[["d", "date"]].itertuples(index=False, name=None))


def iter_sales(
    path: Path, calendar: dict[str, date], selection: Selection
) -> Iterator[pd.DataFrame]:
    columns = META_COLUMNS + list(calendar)
    check_header(path, columns)
    seen: set[tuple[str, str]] = set()
    observed = {
        "store_ids": set(),
        "item_ids": set(),
        "department_ids": set(),
        "category_ids": set(),
    }
    filters = {
        "store_ids": "store_id",
        "item_ids": "item_id",
        "department_ids": "dept_id",
        "category_ids": "cat_id",
    }
    # Read only requested date columns; select series before expanding their days.
    with pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        usecols=columns,
        chunksize=128,
    ) as reader:
        for frame in reader:
            for field, column in filters.items():
                values = getattr(selection, field)
                if values:
                    frame = frame.loc[frame[column].isin(values)]
            if frame.empty:
                continue
            for column in META_COLUMNS:
                invalid = ~frame[column].str.fullmatch(ID_PATTERN)
                if invalid.any():
                    raise InputError(
                        "invalid_id", f"Invalid {column} in selected sales", int(invalid.sum())
                    )
            for item, store in frame[["item_id", "store_id"]].itertuples(index=False, name=None):
                key = (item, store)
                if key in seen:
                    raise InputError(
                        "duplicate_series", "Repeated item/store row in selected input", 1
                    )
                seen.add(key)
            for field, column in filters.items():
                observed[field].update(frame[column])
            long = frame.melt(id_vars=META_COLUMNS, var_name="day_id", value_name="units_sold")
            valid_units = long["units_sold"].str.fullmatch(r"[0-9]+")
            if not valid_units.all():
                raise InputError(
                    "invalid_units",
                    "Selected sales must contain nonnegative integer units; blanks are not zero",
                    int((~valid_units).sum()),
                )
            try:
                long["units_sold"] = long["units_sold"].astype("int64")
            except (ValueError, OverflowError) as exc:
                raise InputError(
                    "invalid_units", "Selected sales exceed the supported integer range", 1
                ) from exc
            if (long["units_sold"] < 0).any():
                raise InputError(
                    "invalid_units", "Selected sales exceed the supported integer range", 1
                )
            long["date"] = long["day_id"].map(calendar)
            yield long.drop(columns="day_id")
    if not seen:
        raise InputError("empty_selection", "No sales series match the explicit selection")
    for field in filters:
        if set(getattr(selection, field)) - observed[field]:
            raise InputError(
                "unmatched_selection", f"Some requested {field} have no matching series"
            )


def create_control_data(directory: Path) -> None:
    """Own tiny synthetic fixture; not extracted from or attributed to Walmart."""
    directory.mkdir(parents=True, exist_ok=True)
    targets = [directory / "calendar.csv", directory / "sales_train_evaluation.csv"]
    if any(path.exists() for path in targets):
        raise InputError("control_exists", "Control generation never overwrites existing files")
    with targets[0].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["d", "date"])
        for index in range(3):
            writer.writerow([f"d_{index + 1}", date(2020, 1, 1) + timedelta(days=index)])
    with targets[1].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(META_COLUMNS + ["d_1", "d_2", "d_3"])
        writer.writerows(
            [
                ["DEMO_ITEM_A", "DEMO_STORE", "DEMO_DEPT", "DEMO_CAT", "DEMO_STATE", 2, 0, 4],
                ["DEMO_ITEM_B", "DEMO_STORE", "DEMO_DEPT", "DEMO_CAT", "DEMO_STATE", 1, 3, 0],
            ]
        )
