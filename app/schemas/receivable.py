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
    module_id: UUID  # Required in new workflow - must specify which module this receivable is for
    payment_type: PaymentType = PaymentType.MODULE_BASED  # Default to module-based

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
    def validate_module_id(cls, v):
        if v is None:
            raise ValueError('module_id is required in the new workflow')
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
    module_id: Optional[UUID] = None  # Always present in new workflow
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = None
    status: ReceivableStatus
    payment_type: PaymentType
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: Optional[UUID] = None
    derived: ReceivableDerived
    
    # Related data
    module: Optional[ProjectModuleResponse] = None   # Always present since module_id is required
    client_name: Optional[str] = None  # From bid
    project_title: Optional[str] = None  # From bid + module

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
    module_name: str  # Always present since modules are required

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
    bid_id: Optional[UUID] = None  # Added for filtering by specific bid

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
    modules_with_receivables: int = 0  # New field
    modules_without_receivables: int = 0  # New field


class BidReceivableResponse(BaseModel):
    """Response for bid with its receivables and modules."""
    bid_id: UUID
    job_title: str
    client_name: str
    has_modules: bool
    total_contract_value: Decimal
    receivables: List[ReceivableResponse]
    modules: List[ProjectModuleResponse]
    
    # Workflow status indicators
    modules_count: int = 0
    receivables_count: int = 0
    pending_modules: int = 0  # Modules without receivables
    
    class Config:
        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        # Calculate derived fields
        if 'modules' in data:
            self.modules_count = len(data['modules'])
        if 'receivables' in data:
            self.receivables_count = len(data['receivables'])
            # Calculate pending modules (modules without receivables)
            if 'modules' in data:
                module_ids_with_receivables = {r.module_id for r in data['receivables']}
                module_ids = {m.id for m in data['modules']}
                self.pending_modules = len(module_ids - module_ids_with_receivables)


# Legacy schemas for backward compatibility (if needed)
class LegacyReceivableCreate(ReceivableBase):
    """Legacy schema for creating receivables without modules (deprecated)."""
    bid_id: UUID
    module_id: Optional[UUID] = None
    payment_type: PaymentType = PaymentType.SINGLE

    @validator('payment_type')
    def validate_legacy_payment_type(cls, v, values):
        # In legacy mode, warn about deprecation
        import warnings
        warnings.warn(
            "Single payment type without modules is deprecated. Use module-based workflow.",
            DeprecationWarning
        )
        return v