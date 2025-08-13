from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date
from uuid import UUID
from dependencies.dependencies import (
    get_db, get_current_user, get_current_admin_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentAdminUser, CurrentSubAdminUser
)
from services.analytics_service import AnalyticsService
from schemas.analytics import (
    AnalyticsScope, DashboardAnalytics, ReportRequest, ReportResponse,
    BidPerformanceReport, FinancialReport, OperationalReport
)
from schemas.common import ExportRequest, ExportResponse
from models.models import UserRole
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()


@router.get("/analytics/dashboard", response_model=DashboardAnalytics)
async def get_dashboard_analytics(
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: str = Query(..., pattern="^(admin|team|member)$", description="Analytics scope"),
    team_id: Optional[str] = Query(None, description="Team ID for team scope"),
    user_id: Optional[str] = Query(None, description="User ID for member scope"),
    range: str = Query("month", pattern="^(day|week|month|custom)$", description="Time range"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Start date for custom range"),
    to_date: Optional[datetime] = Query(None, alias="to", description="End date for custom range"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get dashboard analytics with role-based access control.
    
    **Scope Access Rules:**
    - Admin: Can access admin, team, and member scopes
    - Sub-Admin: Can access team and member scopes for their team
    - Member: Can only access member scope for themselves
    
    **Parameters:**
    - **scope**: admin (system-wide), team (team-specific), member (individual)
    - **team_id**: Required for team scope, optional for admin scope
    - **user_id**: Required for member scope
    - **range**: Time range (day, week, month, custom)
    - **from_date**: Start date for custom range
    - **to_date**: End date for custom range
    """
    try:
        # Parse UUIDs if provided
        team_uuid = UUID(team_id) if team_id else None
        user_uuid = UUID(user_id) if user_id else None
        
        # Validate scope access
        if not _validate_scope_access(scope, current_user, team_uuid, user_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for requested scope"
            )
        
        scope_data = AnalyticsScope(
            scope=scope,
            team_id=team_uuid,
            user_id=user_uuid,
            range=range,
            from_date=from_date,
            to_date=to_date
        )
        
        return analytics_service.get_dashboard_analytics(
            db, scope_data, current_user.id, 
            current_user.role, current_user.team_id
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format: {e}"
        )


@router.post("/analytics/reports", response_model=ReportResponse)
async def generate_report(
    report_request: ReportRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Generate analytics report.
    
    **Report Types:**
    - **bid_performance**: Bid success rates, trends, and patterns
    - **financial**: Revenue, costs, profit margins, receivables
    - **operational**: Team productivity, efficiency metrics
    
    **Access Control:**
    - Admin: Can generate any report with any filters
    - Sub-Admin: Can generate reports for their team
    - Member: Can generate personal reports only
    """
    return analytics_service.generate_report(
        db, report_request, current_user.id,
        current_user.role, current_user.team_id
    )


@router.post("/analytics/export", response_model=ExportResponse)
async def export_analytics(
    export_request: ExportRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Export analytics data in various formats.
    
    **Export Formats:**
    - **csv**: Comma-separated values
    - **xlsx**: Microsoft Excel format
    - **pdf**: Portable Document Format
    - **json**: JavaScript Object Notation
    
    **Export Types:**
    - **bid_performance**: Bid data and statistics
    - **financial**: Financial reports and summaries
    - **operational**: Operational metrics and KPIs
    """
    return analytics_service.export_analytics(
        db, export_request, current_user.id,
        current_user.role, current_user.team_id
    )


# Detailed report endpoints
@router.get("/analytics/reports/bid-performance", response_model=BidPerformanceReport)
async def get_bid_performance_report(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get detailed bid performance report.
    
    Includes:
    - Overall bid statistics
    - Team performance breakdown
    - Member performance breakdown
    - Vertical performance breakdown
    - Performance trends over time
    """
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        # Validate access
        if team_uuid and not _can_access_team_data(current_user, team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for specified team"
            )
        
        return analytics_service.get_bid_performance_report(
            db, team_uuid, date_from, date_to,
            current_user.role, current_user.team_id
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.get("/analytics/reports/financial", response_model=FinancialReport)
async def get_financial_report(
     current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get detailed financial report.
    
    Includes:
    - Revenue summaries
    - Cost breakdowns
    - Profit analysis
    - Receivables status
    - Monthly trends
    """
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        # Validate access
        if team_uuid and not _can_access_team_data(current_user, team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for specified team"
            )
        
        return analytics_service.get_financial_report(
            db, team_uuid, date_from, date_to,
            current_user.role, current_user.team_id
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.get("/analytics/reports/operational", response_model=OperationalReport)
async def get_operational_report(
     current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get detailed operational report.
    
    Includes:
    - Productivity metrics
    - Efficiency indicators
    - Quality measurements
    - Team utilization
    """
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        # Validate access
        if team_uuid and not _can_access_team_data(current_user, team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for specified team"
            )
        
        return analytics_service.get_operational_report(
            db, team_uuid, date_from, date_to,
            current_user.role, current_user.team_id
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


# Advanced analytics endpoints
@router.get("/analytics/insights", response_model=dict)
async def get_performance_insights(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Team ID for team insights"),
    user_id: Optional[str] = Query(None, description="User ID for member insights"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get AI-powered performance insights and recommendations.
    """
    try:
        team_uuid = UUID(team_id) if team_id else None
        user_uuid = UUID(user_id) if user_id else None
        
        # Validate access
        if team_uuid and not _can_access_team_data(current_user, team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for specified team"
            )
        
        if user_uuid and not _can_access_user_data(current_user, user_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for specified user"
            )
        
        return analytics_service.get_performance_insights(
            db, team_uuid, user_uuid, current_user.role
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )


@router.get("/analytics/predictions", response_model=dict)
async def get_predictive_analytics(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Team ID"),
    user_id: Optional[str] = Query(None, description="User ID"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get predictive analytics for future performance.
    """
    try:
        team_uuid = UUID(team_id) if team_id else None
        user_uuid = UUID(user_id) if user_id else None
        
        # Validate access
        if team_uuid and not _can_access_team_data(current_user, team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for specified team"
            )
        
        if user_uuid and not _can_access_user_data(current_user, user_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for specified user"
            )
        
        return analytics_service.get_predictive_analytics(
            db, team_uuid, user_uuid, current_user.role
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )


# Helper functions for access validation
def _validate_scope_access(scope: str, user, team_id: Optional[UUID], user_id: Optional[UUID]) -> bool:
    """Validate if user can access the requested scope."""
    if user.role == UserRole.ADMIN:
        return True
    
    if scope == "admin":
        return user.role == UserRole.ADMIN
    
    if scope == "team":
        if user.role == UserRole.SUB_ADMIN:
            return not team_id or team_id == user.team_id
        return False
    
    if scope == "member":
        if user.role == UserRole.ADMIN:
            return True
        if user.role == UserRole.SUB_ADMIN:
            # Sub-admin can view member data for their team members
            return True  # Additional validation needed in service layer
        if user.role == UserRole.MEMBER:
            return not user_id or user_id == user.id
    
    return False


def _can_access_team_data(user, team_id: UUID) -> bool:
    """Check if user can access team data."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.SUB_ADMIN:
        return team_id == user.team_id
    return False


def _can_access_user_data(user, user_id: UUID) -> bool:
    """Check if user can access user data."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.SUB_ADMIN:
        # Additional validation needed to check if user is in same team
        return True
    if user.role == UserRole.MEMBER:
        return user_id == user.id
    return False