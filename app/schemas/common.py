from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar, List, Any
from datetime import datetime
from uuid import UUID

T = TypeVar('T')


class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[str] = None
    count: int
    

class SuccessResponse(BaseResponse):
    success: bool = True


class ErrorResponse(BaseResponse):
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[dict] = None


class DateRange(BaseModel):
    from_date: Optional[datetime] = Field(alias="from")
    to_date: Optional[datetime] = Field(alias="to")


class SortOrder(BaseModel):
    field: str
    direction: str = Field(regex="^(asc|desc)$", default="desc")


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: Optional[str] = None
    sort: Optional[str] = None  # e.g., "-created_at"


class FilterParams(BaseModel):
    q: Optional[str] = None  # Search query
    status: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ExportRequest(BaseModel):
    type: str = Field(regex="^(bid_performance|financial|operational)$")
    format: str = Field(regex="^(csv|xlsx|pdf|json)$")
    filters: Optional[dict] = None


class ExportResponse(BaseModel):
    export_id: UUID
    status: str = Field(regex="^(queued|processing|ready)$")
    download_url: Optional[str] = None