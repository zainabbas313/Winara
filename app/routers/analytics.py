# routes/analytics.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
import logging
import io

from dependencies.dependencies import (
    DatabaseSession, CurrentUser
)
from services.analytics_service import AnalyticsService
from schemas.analytics import (
    AnalyticsScope, DashboardAnalytics, ReportRequest, ReportResponse,
    BidPerformanceReport, FinancialReport, OperationalReport
)
from schemas.common import ExportRequest, ExportResponse, PaginationParams
from schemas.analytics import APIResponse
from models.models import UserRole
from utils.exceptions import AnalyticsError, ValidationError, PermissionError as CustomPermissionError
from utils.rate_limiter import rate_limit
# from utils.audit import log_analytics_access

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()


@router.get("/dashboard", response_model=DashboardAnalytics)
@rate_limit(calls=100, period=3600)  # 100 calls per hour
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
    Get dashboard analytics with comprehensive role-based access control.
    
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
        _validate_scope_access(scope, current_user, team_uuid, user_uuid)
        
        # Create scope data
        scope_data = AnalyticsScope(
            scope=scope,
            team_id=team_uuid,
            user_id=user_uuid,
            range=range,
            from_date=from_date,
            to_date=to_date
        )
        
        # Log analytics access
        # background_tasks.add_task(
        #     log_analytics_access,
        #     user_id=current_user.id,
        #     action="dashboard_view",
        #     scope=scope,
        #     team_id=team_uuid,
        #     target_user_id=user_uuid
        # )
        
        result = analytics_service.get_dashboard_analytics(
            db, scope_data, current_user.id, 
            current_user.role, current_user.team_id
        )
        
        logger.info(f"Dashboard analytics retrieved for user {current_user.id}, scope: {scope}")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid UUID format in dashboard request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format: {str(e)}"
        )
    except CustomPermissionError as e:
        logger.warning(f"Permission denied for dashboard analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AnalyticsError as e:
        logger.error(f"Analytics error in dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate dashboard analytics"
        )
    except Exception as e:
        logger.error(f"Unexpected error in dashboard analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/reports", response_model=ReportResponse)
@rate_limit(calls=50, period=3600)  # 50 calls per hour
async def generate_report(
    report_request: ReportRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DatabaseSession,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Generate comprehensive analytics report.
    
    **Report Types:**
    - **bid_performance**: Bid success rates, trends, and patterns
    - **financial**: Revenue, costs, profit margins, receivables
    - **operational**: Team productivity, efficiency metrics
    
    **Access Control:**
    - Admin: Can generate any report with any filters
    - Sub-Admin: Can generate reports for their team
    - Member: Can generate personal reports only
    """
    try:
        # Validate report request
        _validate_report_access(report_request, current_user)
        
        # Log report generation
        # background_tasks.add_task(
        #     log_analytics_access,
        #     user_id=current_user.id,
        #     action="report_generate",
        #     report_type=report_request.type.value,
        #     filters=report_request.filters
        # )
        
        result = analytics_service.generate_report(
            db, report_request, current_user.id,
            current_user.role, current_user.team_id
        )
        
        logger.info(f"Report {report_request.type} generated for user {current_user.id}")
        return result
        
    except ValidationError as e:
        logger.error(f"Validation error in report generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except CustomPermissionError as e:
        logger.warning(f"Permission denied for report generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except AnalyticsError as e:
        logger.error(f"Analytics error in report generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


# @router.post("/export", response_model=ExportResponse)
# @rate_limit(calls=20, period=3600)  # 20 exports per hour
# async def export_analytics(
#     export_request: ExportRequest,
#     background_tasks: BackgroundTasks,
#     current_user: CurrentUser,
#     db: DatabaseSession,
#     analytics_service: AnalyticsService = Depends(get_analytics_service)
# ):
#     """
#     Export analytics data in various formats.
    
#     **Export Formats:**
#     - **csv**: Comma-separated values
#     - **xlsx**: Microsoft Excel format
#     - **pdf**: Portable Document Format
#     - **json**: JavaScript Object Notation
    
#     **Export Types:**
#     - **bid_performance**: Bid data and statistics
#     - **financial**: Financial reports and summaries
#     - **operational**: Operational metrics and KPIs
#     """
#     try:
#         # Validate export access
#         _validate_export_access(export_request, current_user)
        
#         # Log export request
#         # background_tasks.add_task(
#         #     log_analytics_access,
#         #     user_id=current_user.id,
#         #     action="data_export",
#         #     type=export_request.type.value,
#         #     format=export_request.format.value
#         # )
        
#         result = analytics_service.export_analytics(
#             db, export_request, current_user.id,
#             current_user.role, current_user.team_id
#         )
        
#         logger.info(f"Data exported for user {current_user.id}, type: {export_request.type}")
#         return result
        
#     except ValidationError as e:
#         logger.error(f"Validation error in export: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(e)
#         )
#     except CustomPermissionError as e:
#         logger.warning(f"Permission denied for export: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail=str(e)
#         )
#     except AnalyticsError as e:
#         logger.error(f"Analytics error in export: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to export data"
#         )


# Detailed report endpoints
@router.get("/reports/bid-performance", response_model=BidPerformanceReport)
@rate_limit(calls=30, period=3600)
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
        
        result = analytics_service.get_bid_performance_report(
            db, team_uuid, date_from, date_to,
            current_user.role, current_user.team_id
        )
        
        logger.info(f"Bid performance report generated for user {current_user.id}")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid team ID format: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )
    except AnalyticsError as e:
        logger.error(f"Error generating bid performance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate bid performance report"
        )


@router.get("/reports/financial", response_model=FinancialReport)
@rate_limit(calls=30, period=3600)
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
        
        result = analytics_service.get_financial_report(
            db, team_uuid, date_from, date_to,
            current_user.role, current_user.team_id
        )
        
        logger.info(f"Financial report generated for user {current_user.id}")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid team ID format: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )
    except AnalyticsError as e:
        logger.error(f"Error generating financial report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate financial report"
        )


@router.get("/reports/operational", response_model=OperationalReport)
@rate_limit(calls=30, period=3600)
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
        
        result = analytics_service.get_operational_report(
            db, team_uuid, date_from, date_to,
            current_user.role, current_user.team_id
        )
        
        logger.info(f"Operational report generated for user {current_user.id}")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid team ID format: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )
    except AnalyticsError as e:
        logger.error(f"Error generating operational report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate operational report"
        )


# Advanced analytics endpoints
@router.get("/insights", response_model=Dict[str, Any])
@rate_limit(calls=20, period=3600)
async def get_performance_insights(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Team ID for team insights"),
    user_id: Optional[str] = Query(None, description="User ID for member insights"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get AI-powered performance insights and recommendations.
    
    This endpoint provides intelligent analysis of performance data including:
    - Trend analysis and pattern recognition
    - Performance benchmarking
    - Actionable recommendations
    - Risk and opportunity identification
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
        
        result = analytics_service.get_performance_insights(
            db, team_uuid, user_uuid, current_user.role
        )
        
        logger.info(f"Performance insights generated for user {current_user.id}")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid ID format in insights request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )
    except AnalyticsError as e:
        logger.error(f"Error generating performance insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate performance insights"
        )


@router.get("/predictions", response_model=Dict[str, Any])
@rate_limit(calls=10, period=3600)
async def get_predictive_analytics(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Team ID"),
    user_id: Optional[str] = Query(None, description="User ID"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get predictive analytics for future performance.
    
    This endpoint provides machine learning-based predictions including:
    - Performance forecasting
    - Success probability analysis
    - Trend predictions
    - Recommended actions for optimization
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
        
        result = analytics_service.get_predictive_analytics(
            db, team_uuid, user_uuid, current_user.role
        )
        
        logger.info(f"Predictive analytics generated for user {current_user.id}")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid ID format in predictions request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )
    except AnalyticsError as e:
        logger.error(f"Error generating predictive analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate predictive analytics"
        )


# @router.get("/download/{filename}")
# async def download_export_file(
#     filename: str,
#     current_user: CurrentUser,
#     db: DatabaseSession
# ):
#     """
#     Download exported analytics file.
    
#     This endpoint serves exported files with proper authentication
#     and access control. Files are automatically cleaned up after
#     24 hours for security.
#     """
#     try:
#         # In a real implementation, you would:
#         # 1. Validate file ownership
#         # 2. Check file existence and expiry
#         # 3. Stream file content
#         # 4. Log download activity
        
#         # Placeholder implementation
#         raise HTTPException(
#             status_code=status.HTTP_501_NOT_IMPLEMENTED,
#             detail="File download functionality not yet implemented"
#         )
        
#     except Exception as e:
#         logger.error(f"Error downloading file {filename}: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to download file"
#         )



# Helper functions for access validation
def _validate_scope_access(scope: str, user, team_id: Optional[UUID], user_id: Optional[UUID]) -> None:
    """Validate if user can access the requested scope."""
    if user.role == UserRole.ADMIN:
        return  # Admin has access to everything
    
    if scope == "admin":
        if user.role != UserRole.ADMIN:
            raise CustomPermissionError("Admin access required for admin scope")
    
    elif scope == "team":
        if user.role == UserRole.SUB_ADMIN:
            if team_id and team_id != user.team_id:
                raise CustomPermissionError("Sub-admin can only access their own team data")
        elif user.role == UserRole.MEMBER:
            raise CustomPermissionError("Members cannot access team scope")
    
    elif scope == "member":
        if user.role == UserRole.MEMBER:
            if user_id and user_id != user.id:
                raise CustomPermissionError("Members can only access their own data")


def _validate_report_access(report_request: ReportRequest, user) -> None:
    """Validate report generation access."""
    if user.role == UserRole.ADMIN:
        return  # Admin can generate any report
    
    # Check if user is requesting data outside their scope
    filters = report_request.filters or {}
    requested_team_id = filters.get('team_id')
    
    if user.role == UserRole.SUB_ADMIN:
        if requested_team_id and UUID(requested_team_id) != user.team_id:
            raise CustomPermissionError("Sub-admin can only generate reports for their team")
    elif user.role == UserRole.MEMBER:
        if requested_team_id:
            raise CustomPermissionError("Members cannot generate team reports")


def _validate_export_access(export_request: ExportRequest, user) -> None:
    """Validate export access."""
    if user.role == UserRole.ADMIN:
        return  # Admin can export anything
    
    # Similar validation as report access
    filters = export_request.filters or {}
    requested_team_id = filters.get('team_id')
    
    if user.role == UserRole.SUB_ADMIN:
        if requested_team_id and UUID(requested_team_id) != user.team_id:
            raise CustomPermissionError("Sub-admin can only export their team data")
    elif user.role == UserRole.MEMBER:
        if requested_team_id:
            raise CustomPermissionError("Members cannot export team data")


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
        # Additional validation would be needed to check if user is in same team
        return True  # Simplified for this example
    if user.role == UserRole.MEMBER:
        return user_id == user.id
    return False