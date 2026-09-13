from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    location: list[str | int]
    message: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"


class SourceInfo(BaseModel):
    filename: str
    sha256: str | None = None
    size_bytes: int | None = None


class LoadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    finished_at: datetime | None
    fingerprint: str | None
    reused_load_id: UUID | None
    parser_version: str
    selection: dict
    sources: list[SourceInfo]
    records_processed: int
    records_rejected: int
    records_inserted: int
    records_unchanged: int
    error_code: str | None
    error_message: str | None


class LoadsResponse(BaseModel):
    items: list[LoadResponse]
    limit: int
    offset: int


class SaleResponse(BaseModel):
    item_id: str
    store_id: str
    date: date
    units_sold: int
    load_id: UUID


class SalesResponse(BaseModel):
    item_id: str
    store_id: str
    start_date: date
    end_date: date
    items: list[SaleResponse]
    next_after_date: date | None
