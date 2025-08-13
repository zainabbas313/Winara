from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from ..models import ReceivableStatus


class ReceivableBase(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    project_title: str = Field(min_length=1, max_length=500)
    contract_value: Decimal = Field(gt=0)
    expected_payment_date: date
    currency: str = Field(default="USD", regex="^[A-Z]{3}$")


class ReceivableCreate(ReceivableBase):
    bid_id: UUID
    team_id: UUID


class ReceivableUpdate(ReceivableBase):
    project_title: Optional[str] = Field(None, min_length=1, max_length=500)
    expected_payment_date: Optional[date] = None
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = Field(None, gt=0)
    status: Optional[ReceivableStatus] = None
    currency: Optional[str] = Field(None, regex="^[A-Z]{3}$")


class ReceivableResponse(ReceivableBase):
    id: UUID
    bid_id: UUID
    team_id: UUID
    actual_payment_date: Optional[date] = None
    payment_amount: Optional[Decimal] = None
    status: ReceivableStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: UUID
    derived: 'ReceivableDerived'

    class Config:
        from_attributes = True


class ReceivableDerived(BaseModel):
    is_overdue: bool
    days_overdue: int


class ReceivableStatusUpdate(BaseModel):
    status: ReceivableStatus


class ReceivableListFilter(BaseModel):
    team_id: Optional[UUID] = None
    status: Optional[ReceivableStatus] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    client_name: Optional[str] = None


class ReceivableSummary(BaseModel):
    id: UUID
    client_name: str
    project_title: str
    contract_value: Decimal
    status: ReceivableStatus
    expected_payment_date: date
    is_overdue: bool

    class Config:
        from_attributes = True


class ReceivableStats(BaseModel):
    total_receivables: int
    total_value: Decimal
    paid_value: Decimal
    pending_value: Decimal
    overdue_value: Decimal
    overdue_count: int
    avg_payment_days: Optional[Decimal] = None


# Fix forward reference
ReceivableResponse.model_rebuild()