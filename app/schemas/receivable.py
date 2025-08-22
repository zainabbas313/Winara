from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from models.models import ReceivableStatus
import re


class ReceivableBase(BaseModel):
    """Base receivable schema with common fields."""
    client_name: str = Field(..., min_length=1, max_length=200, description="Name of the client")
    project_title: str = Field(..., min_length=1, max_length=500, description="Title of the project")
    contract_value: Decimal = Field(..., gt=0, description="Value of the contract")
    expected_payment_date: date = Field(..., description="Expected payment date")
    currency: str = Field(default="USD", description="Currency code")

    @field_validator('currency')
    def validate_currency_code(cls, v: str):
        """Validate currency code format."""
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Currency must be a 3-letter uppercase code (e.g., USD, EUR)')
        return v

    @field_validator('client_name', 'project_title')
    def validate_not_empty(cls, v: str, info: FieldValidationInfo):
        """Validate that strings are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError(f'{info.field_name} cannot be empty or whitespace')
        return v.strip()

    @field_validator('expected_payment_date')
    def validate_payment_date(cls, v: date):
        """Validate that payment date is not too far in the past."""
        return v


class ReceivableCreate(ReceivableBase):
    """Schema for creating a new receivable."""
    bid_id: UUID = Field(..., description="ID of the won bid")
    team_id: UUID = Field(..., description="ID of the team")


class ReceivableUpdate(BaseModel):
    """Schema for updating a receivable."""
    client_name: Optional[str] = Field(None, min_length=1, max_length=200)
    project_title: Optional[str] = Field(None, min_length=1, max_length=500)
    contract_value: Optional[Decimal] = Field(None, gt=0)
    expected_payment_date: Optional[date] = None
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = Field(None, gt=0)
    status: Optional[ReceivableStatus] = None
    currency: Optional[str] = None

    @field_validator('currency')
    def validate_currency_code(cls, v: Optional[str]):
        if v is not None and not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Currency must be a 3-letter uppercase code (e.g., USD, EUR)')
        return v

    @field_validator('client_name', 'project_title')
    def validate_not_empty(cls, v: Optional[str], info: FieldValidationInfo):
        if v is not None:
            if not v.strip():
                raise ValueError(f'{info.field_name} cannot be empty or whitespace')
            return v.strip()
        return v

    @field_validator('actual_payment_date')
    def validate_actual_payment_date(cls, v: Optional[date], info: FieldValidationInfo):
        return v


class ReceivableDerived(BaseModel):
    """Derived fields calculated from receivable data."""
    is_overdue: bool = Field(..., description="Whether the receivable is overdue")
    days_overdue: int = Field(..., description="Number of days overdue (0 if not overdue)")
    days_until_due: int = Field(..., description="Days until due date (negative if overdue)")
    payment_delay: Optional[int] = Field(None, description="Days between expected and actual payment")


class ReceivableResponse(ReceivableBase):
    """Schema for receivable response."""
    id: UUID
    bid_id: UUID
    team_id: Optional[UUID] = None
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = None
    status: ReceivableStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: UUID
    derived: ReceivableDerived

    class Config:
        from_attributes = True
        use_enum_values = True


class ReceivableStatusUpdate(BaseModel):
    """Schema for updating receivable status."""
    status: ReceivableStatus = Field(..., description="New status")
    actual_payment_date: Optional[date] = Field(None, description="Actual payment date if marking as paid")
    payment_amount: Optional[Decimal] = Field(None, gt=0, description="Payment amount if different from contract value")

    @field_validator('payment_amount')
    def validate_payment_with_status(cls, v: Optional[Decimal], info: FieldValidationInfo):
        status = info.data.get('status')
        if status in [ReceivableStatus.PAID, ReceivableStatus.PARTIAL] and v is None:
            raise ValueError('Payment amount is required when marking as paid or partial')
        return v

    @field_validator('actual_payment_date')
    def validate_payment_date_with_status(cls, v: Optional[date], info: FieldValidationInfo):
        status = info.data.get('status')
        if status == ReceivableStatus.PAID and v is None:
            raise ValueError('Actual payment date is required when marking as paid')
        return v


class ReceivableListFilter(BaseModel):
    """Filters for receivable list queries."""
    team_id: Optional[UUID] = Field(None, description="Filter by team ID")
    status: Optional[ReceivableStatus] = Field(None, description="Filter by status")
    date_from: Optional[date] = Field(None, description="Filter from this date (expected payment)")
    date_to: Optional[date] = Field(None, description="Filter until this date (expected payment)")
    client_name: Optional[str] = Field(None, description="Search by client name")
    is_overdue: Optional[bool] = Field(None, description="Filter overdue receivables")
    currency: Optional[str] = Field(None, description="Filter by currency")
    min_value: Optional[Decimal] = Field(None, gt=0, description="Minimum contract value")
    max_value: Optional[Decimal] = Field(None, gt=0, description="Maximum contract value")

    @field_validator('max_value')
    def validate_value_range(cls, v: Optional[Decimal], info: FieldValidationInfo):
        min_value = info.data.get('min_value')
        if v is not None and min_value is not None and v <= min_value:
            raise ValueError('max_value must be greater than min_value')
        return v


class ReceivableSummary(BaseModel):
    """Summary information for a receivable."""
    id: UUID
    client_name: str
    project_title: str
    contract_value: Decimal
    status: ReceivableStatus
    expected_payment_date: date
    actual_payment_date: Optional[date] = None
    is_overdue: bool
    days_overdue: int
    currency: str

    class Config:
        from_attributes = True
        use_enum_values = True


class ReceivableStats(BaseModel):
    """Comprehensive receivable statistics."""
    total_receivables: int
    total_value: Decimal
    paid_value: Decimal
    pending_value: Decimal
    partial_value: Decimal
    overdue_value: Decimal
    overdue_count: int
    avg_payment_days: Optional[Decimal]
    collection_rate: Decimal
    by_status: dict
    by_currency: dict
    current_month_value: Decimal
    next_month_value: Decimal


class ReceivablePaymentTrend(BaseModel):
    """Payment trend data point."""
    date: date
    expected_amount: Decimal
    paid_amount: Decimal
    overdue_amount: Decimal
    receivables_count: int
    payments_count: int


class ReceivableClientSummary(BaseModel):
    """Client summary statistics."""
    client_name: str
    total_receivables: int
    total_value: Decimal
    paid_value: Decimal
    pending_value: Decimal
    overdue_value: Decimal
    avg_payment_days: Optional[Decimal]
    last_payment_date: Optional[date]


class ReceivableCashFlow(BaseModel):
    """Cash flow projection data point."""
    date: date
    expected_inflow: Decimal
    probability_weighted_inflow: Decimal
    cumulative_expected: Decimal
    currency: str


class ReceivableMonthlySummary(BaseModel):
    """Monthly summary statistics."""
    year: int
    month: int
    total_receivables: int
    total_value: Decimal
    paid_value: Decimal
    collection_rate: Decimal
    avg_payment_days: Optional[Decimal]
    overdue_count: int
    overdue_value: Decimal
    by_status: dict
    top_clients: List[ReceivableClientSummary]


# Enable forward references
ReceivableResponse.model_rebuild()
