from pydantic import BaseModel, Field, validator
from typing import List, Optional, Generic, TypeVar, Dict, Any
from datetime import datetime
from uuid import UUID
from typing import Optional 
from schemas.analytics import ReportType, ExportFormat

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
    direction: str = Field(pattern="^(asc|desc)$", default="desc")


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
    type: str = Field(pattern="^(bid_performance|financial|operational)$")
    format: str = Field(pattern="^(csv|xlsx|pdf|json)$")
    filters: Optional[dict] = None


class ExportResponse(BaseModel):
    export_id: UUID
    status: str = Field(pattern="^(queued|processing|ready)$")
    download_url: Optional[str] = None


class VerticalSuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True
    message: str = "Operation completed successfully"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VerticalErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class VerticalPaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response with proper default value handling."""
    items: List[T] = Field(default_factory=list)
    total: int = Field(default=0, ge=0, description="Total number of items")
    skip: int = Field(default=0, ge=0, description="Number of items skipped")
    limit: int = Field(default=20, ge=1, description="Maximum number of items returned")
    has_next: bool = Field(default=False, description="Whether there are more items")
    has_prev: bool = Field(default=False, description="Whether there are previous items")
    page: Optional[int] = Field(default=None, description="Current page number (if applicable)")
    total_pages: Optional[int] = Field(default=None, description="Total number of pages (if applicable)")

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure defaults are calculated
        if self.page is None and self.limit > 0:
            self.page = max(1, (self.skip // self.limit) + 1)
        if self.total_pages is None and self.limit > 0:
            self.total_pages = max(1, (self.total + self.limit - 1) // self.limit)
        
        # Calculate has_next and has_prev if not set
        if 'has_next' not in data:
            self.has_next = (self.skip + self.limit) < self.total
        if 'has_prev' not in data:
            self.has_prev = self.skip > 0

    @classmethod
    def create(cls, items: List[T], total: int, skip: int = 0, limit: int = 20):
        """Helper method to create paginated response with automatic defaults."""
        return cls(
            items=items,
            total=total,
            skip=skip,
            limit=limit
        )


class BaseFilter(BaseModel):
    """Base filter class for common filtering parameters."""
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    created_after: Optional[datetime] = Field(None, description="Filter items created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter items created before this date")
    q: Optional[str] = Field(None, description="Search query")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SortOptions(BaseModel):
    """Standard sorting options."""
    field: str = Field(..., description="Field to sort by")
    direction: str = Field("asc", pattern="^(asc|desc)$", description="Sort direction: asc or desc")


class MetadataResponse(BaseModel):
    """Response with metadata information."""
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: Optional[str] = None
    updated_by_id: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    success_count: int = Field(..., ge=0, description="Number of successful operations")
    failed_count: int = Field(..., ge=0, description="Number of failed operations")
    total_count: int = Field(..., ge=0, description="Total number of operations attempted")
    errors: Optional[List[str]] = Field(None, description="List of error messages for failed operations")
    message: str = "Bulk operation completed"

    def __init__(self, **data):
        super().__init__(**data)
        if 'total_count' not in data:
            self.total_count = self.success_count + self.failed_count


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    success: bool = False
    error: str = "Validation Error"
    detail: str
    field_errors: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[str] = None
    environment: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ExportRequest(BaseModel):
    type: ReportType  # Fixed: use type instead of export_type
    format: ExportFormat
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    include_charts: bool = Field(default=False)
    
    @validator('filters')
    def validate_export_filters(cls, v):
        if v is None:
            return {}
        return v


class ExportResponse(BaseModel):
    filename: str
    content_type: str
    file_size: int = Field(ge=0)
    download_url: str
    expires_at: datetime
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }