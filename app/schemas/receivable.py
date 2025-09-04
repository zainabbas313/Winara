from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from models.models import ReceivableStatus, PaymentType, ModuleStatus


class ReceivableBase(BaseModel):
    """Base receivable schema with common fields."""
    contract_value: Decimal = Field(..., gt=0)
    expected_payment_date: date
    currency: str = Field(default="USD", min_length=3, max_length=3)


class ProjectModuleCreate(BaseModel):
    """Schema for creating a project module."""
    module_name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    module_amount: Decimal = Field(..., gt=0)
    order_sequence: int = Field(default=1, ge=1)


class ProjectModuleResponse(BaseModel):
    """Response schema for project module."""
    id: UUID
    bid_id: UUID
    module_name: str
    description: Optional[str]
    module_amount: Decimal
    order_sequence: int
    status: ModuleStatus
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReceivableCreate(ReceivableBase):
    """Schema for creating a new receivable."""
    bid_id: UUID
    module_id: Optional[UUID] = None  # For module-based payments
    payment_type: PaymentType = PaymentType.SINGLE

    @validator('expected_payment_date')
    def validate_payment_date(cls, v):
        if v <= date.today():
            raise ValueError('Expected payment date must be in the future')
        return v

    @validator('currency')
    def validate_currency(cls, v):
        if not v.isupper() or len(v) != 3:
            raise ValueError('Currency must be a valid 3-letter code in uppercase')
        return v

    @validator('module_id')
    def validate_module_consistency(cls, v, values):
        payment_type = values.get('payment_type')
        if payment_type == PaymentType.MODULE_BASED and v is None:
            raise ValueError('module_id is required for module-based payments')
        if payment_type == PaymentType.SINGLE and v is not None:
            raise ValueError('module_id should be null for single payments')
        return v


class BulkReceivableCreate(BaseModel):
    """Schema for creating receivables for a bid with modules."""
    bid_id: UUID
    modules: List[ProjectModuleCreate]
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @validator('modules')
    def validate_modules(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one module is required')
        return v


class ReceivableUpdate(BaseModel):
    """Schema for updating a receivable."""
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
    module_id: Optional[UUID] = None
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = None
    status: ReceivableStatus
    payment_type: PaymentType
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: Optional[UUID] = None
    derived: ReceivableDerived
    
    # Related data
    module: Optional[ProjectModuleResponse] = None
    client_name: Optional[str] = None  # From bid
    project_title: Optional[str] = None  # From bid or module

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
    payment_type: PaymentType
    module_name: Optional[str] = None

    class Config:
        from_attributes = True


class ReceivableListFilter(BaseModel):
    """Filters for receivable listing."""
    team_id: Optional[UUID] = None
    status: Optional[ReceivableStatus] = None
    payment_type: Optional[PaymentType] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    client_name: Optional[str] = None
    module_id: Optional[UUID] = None

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
    by_payment_type: List[Dict[str, Any]]
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


class BidReceivableResponse(BaseModel):
    """Response for bid with its receivables."""
    bid_id: UUID
    job_title: str
    client_name: str
    has_modules: bool
    total_contract_value: Decimal
    receivables: List[ReceivableResponse]
    modules: List[ProjectModuleResponse]

    class Config:
        from_attributes = True