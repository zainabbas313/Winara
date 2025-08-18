from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from models.models import BudgetType, BidStatus


class BidBase(BaseModel):
    job_title: str = Field(min_length=1, max_length=500)
    job_url: Optional[HttpUrl] = None
    job_description: Optional[str] = None
    client_name: Optional[str] = Field(None, max_length=200)
    budget_type: BudgetType
    budget_min: Optional[Decimal] = Field(None, gt=0)
    budget_max: Optional[Decimal] = Field(None, gt=0)
    hourly_rate: Optional[Decimal] = Field(None, gt=0)
    estimated_hours: int = Field(default=0, ge=0)
    connects_used: int = Field(default=1, ge=1, le=50)
    boost_connects_used: int = Field(default=0, ge=0, le=50)
    proposal_text: Optional[str] = None
    cover_letter: Optional[str] = None
    is_featured: bool = False
    competition_level: int = Field(default=1, ge=1, le=10)
    notes: Optional[str] = None

    @validator('budget_max')
    def budget_max_greater_than_min(cls, v, values):
        if v is not None and 'budget_min' in values and values['budget_min'] is not None:
            assert v >= values['budget_min'], 'budget_max must be greater than or equal to budget_min'
        return v

    @validator('hourly_rate')
    def hourly_rate_required_for_hourly_budget(cls, v, values):
        if values.get('budget_type') == BudgetType.HOURLY:
            assert v is not None, 'hourly_rate is required for hourly budget type'
        return v

    @validator('budget_min', 'budget_max')
    def budget_required_for_fixed_budget(cls, v, values):
        if values.get('budget_type') == BudgetType.FIXED and 'budget_min' in values:
            if 'budget_min' in str(cls.__name__) and v is None:
                assert False, 'budget_min is required for fixed budget type'
        return v


class BidCreate(BidBase):
    vertical_id: UUID
    team_id: UUID


class BidUpdate(BidBase):
    job_title: Optional[str] = Field(None, min_length=1, max_length=500)
    vertical_id: Optional[UUID] = None
    member_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    budget_type: Optional[BudgetType] = None
    status: Optional[BidStatus] = None


class BidResponse(BidBase):
    id: UUID
    vertical_id: UUID
    member_id: UUID
    team_id: UUID
    connect_cost: Decimal
    total_cost: Decimal
    status: BidStatus
    submitted_at: datetime
    last_status_change: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    derived: 'BidDerived'

    class Config:
        from_attributes = True


class BidDerived(BaseModel):
    estimated_value: Optional[Decimal] = None
    days_since_submission: int
    can_edit: bool


class BidStatusUpdate(BaseModel):
    status: BidStatus


class BidListFilter(BaseModel):
    status: Optional[BidStatus] = None
    team_id: Optional[UUID] = None
    member_id: Optional[UUID] = None
    vertical_id: Optional[UUID] = None
    budget_type: Optional[BudgetType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    q: Optional[str] = None


class BidSummary(BaseModel):
    id: UUID
    job_title: str
    status: BidStatus
    budget_type: BudgetType
    connects_used: int
    total_cost: Decimal
    submitted_at: datetime
    member_name: str
    vertical_name: str

    class Config:
        from_attributes = True


class BidStats(BaseModel):
    total_bids: int
    wins: int
    win_rate: Decimal
    total_connects_used: int
    total_cost: Decimal
    avg_response_time_hours: Optional[Decimal] = None


# Fix forward reference
BidResponse.model_rebuild()