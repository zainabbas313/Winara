from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal


class AnalyticsScope(BaseModel):
    scope: str = Field(pattern="^(admin|team|member)$")
    team_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    range: str = Field(default="month", pattern="^(day|week|month|custom)$")
    from_date: Optional[datetime] = Field(alias="from")
    to_date: Optional[datetime] = Field(alias="to")


class KPIData(BaseModel):
    total_bids: int
    wins: int
    win_rate: Decimal
    connect_spend: Decimal
    revenue: Decimal
    profit_margin: Decimal


class ChartDataPoint(BaseModel):
    date: date
    bids: Optional[int] = None
    wins: Optional[int] = None
    revenue: Optional[Decimal] = None


class VerticalBreakdown(BaseModel):
    vertical_id: UUID
    name: str
    wins: int
    revenue: Decimal
    bid_count: int
    win_rate: Decimal


class TeamPerformance(BaseModel):
    team_id: UUID
    team_name: str
    total_bids: int
    wins: int
    win_rate: Decimal
    revenue: Decimal
    connect_spend: Decimal


class MemberPerformance(BaseModel):
    member_id: UUID
    member_name: str
    total_bids: int
    wins: int
    win_rate: Decimal
    revenue: Decimal
    connect_spend: Decimal
    avg_bid_value: Decimal


class DashboardAnalytics(BaseModel):
    kpis: KPIData
    charts: Dict[str, List[Any]]


class ReportRequest(BaseModel):
    type: str = Field(pattern="^(bid_performance|financial|operational)$")
    format: str = Field(default="json", pattern="^(json)$")
    filters: Optional[Dict[str, Any]] = None


class ReportResponse(BaseModel):
    type: str
    generated_at: datetime
    data: Dict[str, Any]


class BidPerformanceReport(BaseModel):
    summary: KPIData
    team_breakdown: List[TeamPerformance]
    member_breakdown: List[MemberPerformance]
    vertical_breakdown: List[VerticalBreakdown]
    trends: List[ChartDataPoint]


class FinancialReport(BaseModel):
    revenue_summary: Dict[str, Decimal]
    cost_summary: Dict[str, Decimal]
    profit_summary: Dict[str, Decimal]
    receivables_summary: Dict[str, Any]
    monthly_trends: List[ChartDataPoint]


class OperationalReport(BaseModel):
    productivity_metrics: Dict[str, Any]
    efficiency_metrics: Dict[str, Any]
    quality_metrics: Dict[str, Any]
    team_utilization: List[TeamPerformance]