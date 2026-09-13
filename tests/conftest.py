import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from demandiq.config import Settings
from demandiq.db import make_engine
from demandiq.ingestion.m5 import Selection, create_control_data


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
