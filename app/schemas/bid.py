from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from models.models import BudgetType, BidStatus, UserRole
from enum import Enum

# Existing schemas (keeping the provided ones)
class BidBase(BaseModel):
    job_title: str = Field(min_length=1, max_length=500)
    job_url: Optional[str] = None
    job_description: Optional[str] = None
    client_name: Optional[str] = Field(None, max_length=200)
    budget_type: BudgetType
    budget_min: Optional[Decimal] = Field(None, gt=0)
    budget_max: Optional[Decimal] = Field(None, gt=0)
    hourly_rate: Optional[Decimal] = Field(None, gt=0)
    estimated_hours: int = Field(default=0, ge=0)
    connects_used: int = Field(default=1, ge=1, le=50)
    boost_connects_used: Optional[int] = Field(default=0, ge=0, le=50000)
    proposal_text: Optional[str] = None
    cover_letter: Optional[str] = None
    is_featured: Optional[bool] = False
    competition_level: Optional[int] = Field(default=1, ge=1, le=10)
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


class BidCreate(BidBase):
    vertical_id: UUID
    team_id: Optional[UUID] = None
    member_id: Optional[UUID] = None


class BidUpdate(BidBase):
    job_title: Optional[str] = Field(None, min_length=1, max_length=500)
    vertical_id: Optional[UUID] = None
    member_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    budget_type: Optional[BudgetType] = None
    status: Optional[BidStatus] = None


class BidDerived(BaseModel):
    estimated_value: Optional[Decimal] = None
    days_since_submission: int
    can_edit: bool


class BidResponse(BidBase):
    id: UUID
    vertical_id: UUID
    member_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    connect_cost: Decimal
    total_cost: Decimal
    status: BidStatus
    submitted_at: datetime
    last_status_change: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    derived: BidDerived

    class Config:
        from_attributes = True


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


# NEW ENHANCED SCHEMAS

# Sorting options
class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class BidSortField(str, Enum):
    SUBMITTED_AT = "submitted_at"
    TOTAL_COST = "total_cost"
    CONNECTS_USED = "connects_used"
    STATUS = "status"
    WIN_RATE = "win_rate"
    TOTAL_BIDS = "total_bids"


# Team statistics
class TeamBidStats(BaseModel):
    team_id: UUID
    team_name: str
    total_bids: int
    total_connects_used: int
    total_connect_cost: Decimal
    wins: int
    win_rate: Decimal
    total_earnings: Decimal
    active_members: int
    avg_bid_value: Optional[Decimal] = None

    class Config:
        from_attributes = True


# Member ranking/bidding list
class MemberBidRanking(BaseModel):
    member_id: UUID
    member_name: str
    email: str
    team_id: Optional[UUID] = None
    team_name: Optional[str] = None
    total_bids: int
    wins: int
    win_rate: Decimal
    total_connects_used: int
    total_connect_cost: Decimal
    total_earnings: Decimal
    avg_bid_value: Optional[Decimal] = None
    last_bid_date: Optional[datetime] = None
    rank: Optional[int] = None

    class Config:
        from_attributes = True


# Earnings response
class EarningsResponse(BaseModel):
    total_earnings: Decimal
    won_bids_count: int
    avg_earnings_per_bid: Decimal
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    breakdown_by_vertical: Optional[List['VerticalEarnings']] = None
    breakdown_by_team: Optional[List['TeamEarnings']] = None
    breakdown_by_member: Optional[List['MemberEarnings']] = None


class VerticalEarnings(BaseModel):
    vertical_id: UUID
    vertical_name: str
    earnings: Decimal
    won_bids: int
    total_bids: int
    win_rate: Decimal

    class Config:
        from_attributes = True


class TeamEarnings(BaseModel):
    team_id: UUID
    team_name: str
    earnings: Decimal
    won_bids: int
    total_bids: int
    win_rate: Decimal

    class Config:
        from_attributes = True


class MemberEarnings(BaseModel):
    member_id: UUID
    member_name: str
    earnings: Decimal
    won_bids: int
    total_bids: int
    win_rate: Decimal

    class Config:
        from_attributes = True


# Enhanced filters
class EnhancedBidFilter(BidListFilter):
    min_connect_cost: Optional[Decimal] = None
    max_connect_cost: Optional[Decimal] = None
    min_estimated_value: Optional[Decimal] = None
    max_estimated_value: Optional[Decimal] = None
    competition_level: Optional[int] = Field(None, ge=1, le=10)
    is_featured: Optional[bool] = None
    sort_field: Optional[BidSortField] = None
    sort_direction: Optional[SortDirection] = SortDirection.DESC


class MemberRankingFilter(BaseModel):
    team_id: Optional[UUID] = None
    vertical_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_bids: Optional[int] = Field(None, ge=0)
    min_win_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    sort_field: BidSortField = BidSortField.WIN_RATE
    sort_direction: SortDirection = SortDirection.DESC


# Bulk operations
class BulkBidOperation(BaseModel):
    bid_ids: List[UUID]
    operation: str  # "update_status", "delete", "assign_team"
    data: dict  # Operation-specific data


class BulkOperationResult(BaseModel):
    success_count: int
    failed_count: int
    total_count: int
    errors: List[str] = []
    updated_bids: List[BidResponse] = []


# Dashboard summary
class DashboardSummary(BaseModel):
    statistics: BidStats
    recent_bids: List[BidSummary]
    top_performers: List[MemberBidRanking] = []
    team_performance: Optional[TeamBidStats] = None
    earnings_this_month: Decimal = Decimal('0')
    pending_bids: int = 0


# Advanced analytics
class BidAnalytics(BaseModel):
    conversion_rate: Decimal
    avg_time_to_response: Optional[Decimal] = None
    top_verticals: List[VerticalEarnings]
    monthly_trends: List['MonthlyTrend']
    performance_metrics: dict


class MonthlyTrend(BaseModel):
    month: str  # YYYY-MM format
    total_bids: int
    wins: int
    win_rate: Decimal
    earnings: Decimal
    connects_used: int


# Fix forward references
EarningsResponse.model_rebuild()
BidAnalytics.model_rebuild()