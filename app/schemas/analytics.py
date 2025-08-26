# schemas/analytics.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal

from models.models import ExportFormat, InsightType, ReportType


class AnalyticsScope(BaseModel):
    scope: str = Field(..., pattern="^(admin|team|member)$")
    team_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    range: str = Field(default="month", pattern="^(day|week|month|custom)$")
    from_date: Optional[datetime] = Field(None, alias="from")
    to_date: Optional[datetime] = Field(None, alias="to")

    @validator('from_date', 'to_date')
    def validate_dates(cls, v):
        if v and v > datetime.now():
            raise ValueError('Date cannot be in the future')
        return v

    @validator('to_date')
    def validate_date_range(cls, v, values):
        if v and 'from_date' in values and values['from_date']:
            if v < values['from_date']:
                raise ValueError('to_date must be after from_date')
        return v

    class Config:
        populate_by_name = True


class KPIData(BaseModel):
    total_bids: int = Field(ge=0)
    wins: int = Field(ge=0)
    win_rate: Decimal = Field(ge=0, le=100)
    connect_spend: Decimal = Field(ge=0)
    revenue: Decimal = Field(ge=0)
    profit_margin: Decimal = Field(ge=-100, le=100)
    
    @validator('wins')
    def wins_not_greater_than_total(cls, v, values):
        if 'total_bids' in values and v > values['total_bids']:
            raise ValueError('wins cannot be greater than total_bids')
        return v

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class ChartDataPoint(BaseModel):
    date: Union[date, str]
    bids: Optional[int] = Field(None, ge=0)
    wins: Optional[int] = Field(None, ge=0)
    revenue: Optional[Decimal] = Field(None, ge=0)
    win_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat()
        }


class VerticalBreakdown(BaseModel):
    vertical_id: UUID
    name: str = Field(min_length=1, max_length=200)
    wins: int = Field(ge=0)
    revenue: Decimal = Field(ge=0)
    bid_count: int = Field(ge=0)
    win_rate: Decimal = Field(ge=0, le=100)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class TeamPerformance(BaseModel):
    team_id: UUID
    team_name: str = Field(min_length=1, max_length=100)
    total_bids: int = Field(ge=0)
    wins: int = Field(ge=0)
    win_rate: Decimal = Field(ge=0, le=100)
    revenue: Decimal = Field(ge=0)
    connect_spend: Decimal = Field(ge=0)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class MemberPerformance(BaseModel):
    member_id: UUID
    member_name: Optional[str] = None
    total_bids: int = Field(ge=0)
    wins: int = Field(ge=0)
    win_rate: Decimal = Field(ge=0, le=100)
    revenue: Decimal = Field(ge=0)
    connect_spend: Decimal = Field(ge=0)
    avg_bid_value: Decimal = Field(ge=0)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class DashboardAnalytics(BaseModel):
    kpis: KPIData
    charts: Dict[str, List[Any]] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    scope: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReportRequest(BaseModel):
    type: ReportType
    format: ExportFormat = ExportFormat.JSON
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('filters')
    def validate_filters(cls, v):
        if v is None:
            return {}
        
        # Validate common filter fields
        if 'date_from' in v and v['date_from']:
            try:
                datetime.fromisoformat(v['date_from'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise ValueError('Invalid date_from format')
        
        if 'date_to' in v and v['date_to']:
            try:
                datetime.fromisoformat(v['date_to'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise ValueError('Invalid date_to format')
                
        return v


class ReportResponse(BaseModel):
    type: ReportType
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    filters_applied: Optional[Dict[str, Any]] = None
    record_count: Optional[int] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BidPerformanceReport(BaseModel):
    summary: KPIData
    team_breakdown: List[TeamPerformance] = Field(default_factory=list)
    member_breakdown: List[MemberPerformance] = Field(default_factory=list)
    vertical_breakdown: List[VerticalBreakdown] = Field(default_factory=list)
    trends: List[ChartDataPoint] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FinancialSummary(BaseModel):
    total_expected: Decimal = Field(ge=0)
    total_received: Decimal = Field(ge=0)
    pending_count: int = Field(ge=0)
    pending_value: Decimal = Field(ge=0)
    overdue_count: int = Field(ge=0)
    overdue_value: Decimal = Field(ge=0)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class CostSummary(BaseModel):
    total_connects_cost: Decimal = Field(ge=0, alias="total_cost")  # alias keeps compatibility
    total_connects_used: int = Field(ge=0)
    avg_cost_per_bid: Decimal = Field(ge=0)
    cost_per_win: Decimal = Field(ge=0)

    # optional extras
    regular_connects: Optional[int] = 0
    boost_connects: Optional[int] = 0
    total_bids: Optional[int] = 0

    class Config:
        populate_by_name = True  # allows aliasing
        json_encoders = {Decimal: lambda v: float(v)}


class ProfitSummary(BaseModel):
    gross_profit: Decimal
    profit_margin: Decimal = Field(ge=-100, le=100)
    net_profit: Decimal
    roi_percentage: Decimal
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class FinancialReport(BaseModel):
    revenue_summary: FinancialSummary
    cost_summary: CostSummary
    profit_summary: ProfitSummary
    receivables_summary: Dict[str, Any] = Field(default_factory=dict)
    monthly_trends: List[ChartDataPoint] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProductivityMetrics(BaseModel):
    total_teams: int = Field(ge=0)
    total_members: int = Field(ge=0)
    bids_per_day: float = Field(ge=0)
    bids_per_member: float = Field(ge=0)
    active_members: int = Field(ge=0)
    
    class Config:
        json_encoders = {
            float: lambda v: round(v, 2)
        }


class EfficiencyMetrics(BaseModel):
    avg_response_time_days: float = Field(ge=0)
    win_rate: float = Field(ge=0, le=100)
    decline_rate: float = Field(ge=0, le=100)
    conversion_rate: float = Field(ge=0, le=100)
    
    class Config:
        json_encoders = {
            float: lambda v: round(v, 2)
        }


class QualityMetrics(BaseModel):
    total_bids: int = Field(ge=0)
    wins: int = Field(ge=0)
    declined: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=10)
    
    class Config:
        json_encoders = {
            float: lambda v: round(v, 2)
        }


class OperationalReport(BaseModel):
    productivity_metrics: ProductivityMetrics
    efficiency_metrics: EfficiencyMetrics
    quality_metrics: QualityMetrics
    team_utilization: List[TeamPerformance] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Insight(BaseModel):
    type: InsightType
    message: str = Field(min_length=10, max_length=500)
    impact: str = Field(pattern="^(low|medium|high|critical)$")
    confidence: float = Field(ge=0, le=1)
    suggested_actions: List[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    action: str = Field(min_length=10, max_length=500)
    priority: str = Field(pattern="^(low|medium|high|urgent)$")
    impact_score: float = Field(ge=0, le=10)
    estimated_effort: str = Field(pattern="^(low|medium|high)$", default="medium")


class PerformanceInsights(BaseModel):
    key_insights: List[Insight] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    benchmarks: Dict[str, float] = Field(default_factory=dict)
    trends: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PredictiveAnalytics(BaseModel):
    next_month_forecast: Dict[str, float] = Field(default_factory=dict)
    success_probability: Dict[str, float] = Field(default_factory=dict)
    recommended_actions: List[Recommendation] = Field(default_factory=list)
    confidence_level: str = Field(pattern="^(low|medium|high)$", default="medium")
    model_accuracy: Optional[float] = Field(None, ge=0, le=1)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ExportRequest(BaseModel):
    export_type: ReportType
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


# schemas/common.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class APIResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort: Optional[str] = Field(default="-created_at")


class PaginatedResponse(BaseModel):
    items: list
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    pages: int = Field(ge=1)
    has_next: bool
    has_prev: bool