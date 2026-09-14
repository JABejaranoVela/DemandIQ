import logging
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEMANDIQ_",
        env_ignore_empty=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = None
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "demandiq"
    postgres_user: str = "demandiq"
    postgres_password: SecretStr = SecretStr("")
    data_dir: Path = Path("data/raw")
    forecast_artifacts_dir: Path = Path("artifacts/forecasting")
    archive_dir: Path = Path("data/archive")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    source: Literal["m5", "synthetic-control"] = "m5"
    m5_store_ids: list[str] = Field(default_factory=list)
    m5_item_ids: list[str] = Field(default_factory=list)
    m5_department_ids: list[str] = Field(default_factory=list)
    m5_category_ids: list[str] = Field(default_factory=list)
    m5_start_date: date | None = None
    m5_end_date: date | None = None

    def connection_url(self) -> URL:
        if self.database_url:
            url = make_url(self.database_url.get_secret_value())
            if url.drivername not in {"postgresql", "postgresql+psycopg"}:
                raise ValueError("Only PostgreSQL with Psycopg 3 is supported")
            return url.set(drivername="postgresql+psycopg")
        if not self.postgres_password.get_secret_value():
            raise ValueError("Set DEMANDIQ_POSTGRES_PASSWORD or DEMANDIQ_DATABASE_URL")
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True
    )
    # SQL statements/parameters can contain input data. Do not log them by default.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
