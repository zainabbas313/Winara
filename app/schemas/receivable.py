from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from models.models import ReceivableStatus


class ReceivableBase(BaseModel):
    """Base receivable schema with common fields."""
    client_name: str = Field(..., min_length=1, max_length=200)
    project_title: str = Field(..., min_length=1, max_length=500)
    contract_value: Decimal = Field(..., gt=0)
    expected_payment_date: date
    currency: str = Field(default="USD", min_length=3, max_length=3)


class ReceivableCreate(ReceivableBase):
    """Schema for creating a new receivable."""
    bid_id: UUID
    team_id: UUID

    @validator('expected_payment_date')
    def validate_payment_date(cls, v):
        if v <= date.today():
            raise ValueError('Expected payment date must be in the future')
        return v

    @validator('currency')
    def validate_currency(cls, v):
        # Basic currency code validation
        if not v.isupper() or len(v) != 3:
            raise ValueError('Currency must be a valid 3-letter code in uppercase')
        return v


class ReceivableUpdate(BaseModel):
    """Schema for updating a receivable."""
    client_name: Optional[str] = Field(None, min_length=1, max_length=200)
    project_title: Optional[str] = Field(None, min_length=1, max_length=500)
    contract_value: Optional[Decimal] = Field(None, gt=0)
    expected_payment_date: Optional[date] = None
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = Field(None, ge=0)
    status: Optional[ReceivableStatus] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)

    @validator('payment_amount')
    def validate_payment_amount(cls, v, values):
        if v is not None and v < 0:
            raise ValueError('Payment amount cannot be negative')
        return v

    @validator('actual_payment_date')
    def validate_actual_payment_date(cls, v, values):
        if v is not None and v > date.today():
            raise ValueError('Actual payment date cannot be in the future')
        return v

    @validator('currency')
    def validate_currency(cls, v):
        if v is not None and (not v.isupper() or len(v) != 3):
            raise ValueError('Currency must be a valid 3-letter code in uppercase')
        return v


class ReceivableStatusUpdate(BaseModel):
    """Schema for updating receivable status."""
    status: ReceivableStatus
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = Field(None, ge=0)

    @validator('payment_amount')
    def validate_payment_amount(cls, v, values):
        status = values.get('status')
        if status == ReceivableStatus.PAID and v is None:
            raise ValueError('Payment amount is required when marking as paid')
        if v is not None and v < 0:
            raise ValueError('Payment amount cannot be negative')
        return v

    @validator('actual_payment_date')
    def validate_actual_payment_date(cls, v, values):
        status = values.get('status')
        if status == ReceivableStatus.PAID and v is None:
            # Default to today if not provided
            return date.today()
        if v is not None and v > date.today():
            raise ValueError('Actual payment date cannot be in the future')
        return v


class ReceivableDerived(BaseModel):
    """Derived/calculated fields for receivables."""
    is_overdue: bool
    days_overdue: int
    days_until_due: int
    payment_delay: Optional[int] = None


class ReceivableResponse(ReceivableBase):
    """Response schema for receivable data."""
    id: UUID
    bid_id: UUID
    team_id: UUID
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = None
    status: ReceivableStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: Optional[UUID] = None
    derived: ReceivableDerived

    class Config:
        from_attributes = True


class ReceivableSummary(BaseModel):
    """Summary schema for dashboard and lists."""
    id: UUID
    client_name: str
    project_title: str
    contract_value: Decimal
    status: ReceivableStatus
    expected_payment_date: date
    is_overdue: bool

    class Config:
        from_attributes = True


class ReceivableListFilter(BaseModel):
    """Filters for receivable listing."""
    team_id: Optional[UUID] = None
    status: Optional[ReceivableStatus] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    client_name: Optional[str] = None

    @validator('date_to')
    def validate_date_range(cls, v, values):
        date_from = values.get('date_from')
        if date_from and v and v < date_from:
            raise ValueError('date_to must be after date_from')
        return v


class ReceivableStats(BaseModel):
    """Statistics schema for receivables."""
    total_receivables: int
    total_value: Decimal
    paid_value: Decimal
    pending_value: Decimal
    partial_value: Decimal
    overdue_value: Decimal
    overdue_count: int
    avg_payment_days: Optional[Decimal]
    collection_rate: Decimal
    by_status: List[Dict[str, Any]]
    by_currency: List[Dict[str, Any]]
    current_month_value: Decimal
    next_month_value: Decimal


class ReceivableMonthlyStats(BaseModel):
    """Monthly statistics schema."""
    year: int
    month: int
    total_receivables: int
    expected_value: Decimal
    actual_received: Decimal
    status_breakdown: List[Dict[str, Any]]


class ReceivablePaymentTrend(BaseModel):
    """Payment trend data point."""
    date: str
    expected_count: int
    expected_value: float
    paid_count: int
    paid_value: float
    payment_rate: float


class ReceivableClientSummary(BaseModel):
    """Client summary statistics."""
    client_name: str
    total_receivables: int
    total_value: float
    paid_value: float
    overdue_count: int
    payment_rate: float


class ReceivableCashFlow(BaseModel):
    """Cash flow projection data point."""
    date: str
    daily_amount: float
    cumulative_amount: float