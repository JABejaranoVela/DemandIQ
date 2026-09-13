import csv
from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from demandiq.ingestion.archive import archive_source
from demandiq.ingestion.m5 import InputError, Selection, fingerprint, iter_sales, read_calendar


def test_transform_preserves_zero_and_totals(control_dir, selection):
    calendar = read_calendar(control_dir / "calendar.csv", selection)
    result = pd.concat(iter_sales(control_dir / "sales_train_evaluation.csv", calendar, selection))
    assert len(result) == 6
    assert result.units_sold.sum() == 10
    assert (result.units_sold == 0).sum() == 2
    assert set(result.date) == {date(2020, 1, day) for day in (1, 2, 3)}


def test_explicit_selection_before_expansion(control_dir, selection):
    selection = selection.model_copy(
        update={"item_ids": ["DEMO_ITEM_A"], "end_date": date(2020, 1, 2)}
    )
    calendar = read_calendar(control_dir / "calendar.csv", selection)
    result = pd.concat(iter_sales(control_dir / "sales_train_evaluation.csv", calendar, selection))
    assert result.units_sold.tolist() == [2, 0]
    assert set(result.item_id) == {"DEMO_ITEM_A"}


@pytest.mark.parametrize("value", ["", "NaN", "-1", "1.5", "unknown", "9223372036854775808"])
def test_invalid_units_are_not_zero(control_dir, selection, value):
    path = control_dir / "sales_train_evaluation.csv"
    rows = list(csv.reader(path.open(encoding="utf-8")))
    rows[1][-2] = value
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    with pytest.raises(InputError, match="units|integer|range"):
        list(iter_sales(path, read_calendar(control_dir / "calendar.csv", selection), selection))


@pytest.mark.parametrize("replacement", ["2020-02-31", "not-a-date", "2020-1-01"])
def test_invalid_calendar_dates(control_dir, selection, replacement):
    path = control_dir / "calendar.csv"
    path.write_text(path.read_text().replace("2020-01-01", replacement))
    with pytest.raises(InputError):
        read_calendar(path, selection)


def test_missing_calendar_day_is_not_filled(control_dir, selection):
    path = control_dir / "calendar.csv"
    path.write_text("d,date\nd_1,2020-01-01\nd_3,2020-01-03\n")
    with pytest.raises(InputError, match="entire requested"):
        read_calendar(path, selection)


def test_duplicate_calendar_is_rejected(control_dir, selection):
    path = control_dir / "calendar.csv"
    with path.open("a") as handle:
        handle.write("d_1,2020-01-01\n")
    with pytest.raises(InputError, match="unique"):
        read_calendar(path, selection)


def test_duplicate_source_series_is_rejected(control_dir, selection):
    path = control_dir / "sales_train_evaluation.csv"
    with path.open("a") as handle:
        handle.write(path.read_text().splitlines()[1] + "\n")
    with pytest.raises(InputError, match="Repeated"):
        list(iter_sales(path, read_calendar(control_dir / "calendar.csv", selection), selection))


def test_missing_column_is_rejected(control_dir, selection):
    path = control_dir / "sales_train_evaluation.csv"
    path.write_text(path.read_text().replace("d_2", "missing_day"))
    with pytest.raises(InputError, match="columns"):
        list(iter_sales(path, read_calendar(control_dir / "calendar.csv", selection), selection))


def test_duplicate_column_is_rejected(control_dir, selection):
    path = control_dir / "sales_train_evaluation.csv"
    path.write_text(path.read_text().replace("d_2", "d_1"))
    with pytest.raises(InputError, match="Duplicate columns"):
        list(iter_sales(path, read_calendar(control_dir / "calendar.csv", selection), selection))


def test_invalid_metadata_is_rejected(control_dir, selection):
    path = control_dir / "sales_train_evaluation.csv"
    path.write_text(path.read_text().replace("DEMO_CAT", "bad/category"))
    with pytest.raises(InputError, match="Invalid cat_id"):
        list(iter_sales(path, read_calendar(control_dir / "calendar.csv", selection), selection))


def test_empty_and_unmatched_selection(control_dir, selection):
    calendar = read_calendar(control_dir / "calendar.csv", selection)
    for stores in (["UNKNOWN"], ["DEMO_STORE", "UNKNOWN"]):
        chosen = selection.model_copy(update={"store_ids": stores})
        with pytest.raises(InputError):
            list(iter_sales(control_dir / "sales_train_evaluation.csv", calendar, chosen))


def test_selection_requires_dates_and_store():
    with pytest.raises(ValidationError):
        Selection(store_ids=[])
    with pytest.raises(ValidationError):
        Selection(store_ids=["X"], start_date="2020-02-01", end_date="2020-01-01")


def test_fingerprint_canonicalizes_selection(selection):
    sources = [{"filename": "sales.csv", "sha256": "abc"}]
    first = selection.model_copy(update={"store_ids": ["B", "A", "A"]})
    second = selection.model_copy(update={"store_ids": ["A", "B"]})
    assert fingerprint("m5", sources, first) == fingerprint("m5", sources, second)
    assert fingerprint("m5", sources, first) != fingerprint("synthetic-control", sources, first)
    assert fingerprint("m5", sources, first) != fingerprint(
        "m5", [{"filename": "sales.csv", "sha256": "changed"}], first
    )


def test_archive_preserves_bytes_and_detects_corruption(control_dir, tmp_path):
    source = control_dir / "calendar.csv"
    archive = tmp_path / "archive"
    first = archive_source(source, archive)
    assert archive_source(source, archive) == first
    destination = archive / first["archive_name"]
    assert destination.read_bytes() == source.read_bytes()
    destination.write_text("corrupted")
    with pytest.raises(InputError, match="checksum"):
        archive_source(source, archive)


def test_missing_file(tmp_path):
    with pytest.raises(InputError, match="Required file"):
        archive_source(tmp_path / "missing.csv", tmp_path / "archive")
