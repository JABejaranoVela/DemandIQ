import csv
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from demandiq.config import Settings
from demandiq.db import make_engine
from demandiq.ingestion.m5 import META_COLUMNS, InputError, Selection


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


@pytest.fixture
def control_dir(tmp_path):
    directory = tmp_path / "control"
    create_control_data(directory)
    return directory


@pytest.fixture
def selection():
    return Selection(store_ids=["DEMO_STORE"], start_date="2020-01-01", end_date="2020-01-03")


@pytest.fixture
def settings(control_dir, tmp_path):
    return Settings(
        data_dir=control_dir,
        archive_dir=tmp_path / "archive",
        source="synthetic-control",
    )


@pytest.fixture(scope="session")
def database_engine():
    if os.environ.get("DEMANDIQ_RUN_DB_TESTS") != "1":
        pytest.skip("Set DEMANDIQ_RUN_DB_TESTS=1 and use a disposable PostgreSQL *_test database")
    config = Settings()
    url = config.connection_url()
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("Database tests refuse any database whose name does not end in _test")
    engine = make_engine(config)
    migration = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        migration.attributes["connection"] = connection
        command.upgrade(migration, "head")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(database_engine):
    statement = text("TRUNCATE core.sales, core.products, core.stores, raw.ingestion_loads")
    with database_engine.begin() as connection:
        connection.execute(statement)
    yield database_engine
    with database_engine.begin() as connection:
        connection.execute(statement)
