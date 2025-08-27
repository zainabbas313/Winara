from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import logging

from dependencies.dependencies import (
    get_db, get_current_user, get_current_sub_admin_user, get_current_admin_user,
    DatabaseSession, CurrentUser, CurrentSubAdminUser, CurrentAdminUser
)
from services.bid_service import BidService
from schemas.bid import (
    BidCreate, BidUpdate, BidResponse, BidListFilter, EnhancedBidFilter,
    BidStatusUpdate, BidStats, TeamBidStats, MemberBidRanking, EarningsResponse,
    BidAnalytics, MemberRankingFilter, BulkOperationResult, DashboardSummary,
    BidSummary, MonthlyTrend, BidSortField, SortDirection, BulkBidOperation
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, BidStatus, BudgetType

logger = logging.getLogger(__name__)
router = APIRouter()

# Dependency injection
def get_bid_service() -> BidService:
    return BidService()

# =====================================================================
# FIXED PATHS FIRST (so they don't conflict with dynamic ones)
# =====================================================================

@router.get("/teams/statistics", response_model=List[TeamBidStats])
async def get_team_statistics(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Specific team ID (Admin only)"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get team bid statistics (all or filtered by team_id)."""
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Members cannot access team statistics"
        )

    try:
        team_uuid = UUID(team_id) if team_id else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )

    try:
        return bid_service.get_team_statistics(
            db, team_uuid, current_user.role, current_user.team_id
        )
    except Exception as e:
        logger.exception("Error fetching team statistics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching team statistics: {str(e)}"
        )


@router.get("/bids/statistics", response_model=BidStats)
async def get_bid_statistics(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    member_id: Optional[str] = Query(None, description="Filter by member ID"),
    vertical_id: Optional[str] = Query(None, description="Filter by vertical ID"),
    date_from: Optional[datetime] = Query(None, description="Filter from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter until this date"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get bid statistics with role-based filtering."""
    try:
        team_uuid = UUID(team_id) if team_id else None
        member_uuid = UUID(member_id) if member_id else None
        vertical_uuid = UUID(vertical_id) if vertical_id else None
        
        return bid_service.get_bid_statistics(
            db, team_uuid, member_uuid, vertical_uuid,
            current_user.role, current_user.team_id, date_from, date_to
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.get("/bids/enhanced", response_model=PaginatedResponse[BidResponse])
async def get_bids_enhanced(
    current_user: CurrentUser,
    db: DatabaseSession,
    status_filter: Optional[BidStatus] = Query(None, alias="status", description="Filter by bid status"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    member_id: Optional[str] = Query(None, description="Filter by member ID"),
    vertical_id: Optional[str] = Query(None, description="Filter by vertical ID"),
    budget_type: Optional[BudgetType] = Query(None, description="Filter by budget type"),
    date_from: Optional[datetime] = Query(None, description="Filter bids from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter bids until this date"),
    q: Optional[str] = Query(None, description="Search query"),
    min_connect_cost: Optional[float] = Query(None, description="Minimum connect cost"),
    max_connect_cost: Optional[float] = Query(None, description="Maximum connect cost"),
    competition_level: Optional[int] = Query(None, ge=1, le=10, description="Competition level"),
    is_featured: Optional[bool] = Query(None, description="Filter by featured status"),
    sort_field: Optional[BidSortField] = Query(None, description="Sort field"),
    sort_direction: Optional[SortDirection] = Query(SortDirection.DESC, description="Sort direction"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get bids with enhanced filtering options."""
    try:
        filters = EnhancedBidFilter(
            status=status_filter,
            team_id=UUID(team_id) if team_id and team_id.strip() else None,
            member_id=UUID(member_id) if member_id and member_id.strip() else None,
            vertical_id=UUID(vertical_id) if vertical_id and vertical_id.strip() else None,
            budget_type=budget_type,
            date_from=date_from,
            date_to=date_to,
            q=q,
            min_connect_cost=min_connect_cost,
            max_connect_cost=max_connect_cost,
            competition_level=competition_level,
            is_featured=is_featured,
            sort_field=sort_field,
            sort_direction=sort_direction
        )

        return bid_service.get_bids_enhanced(
            db, filters, current_user.id, current_user.role,
            skip, limit, current_user.team_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching bids: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while retrieving bids"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in get_bids_enhanced: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request"
        )


@router.get("/bids/recent", response_model=List[BidResponse])
async def get_recent_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(10, ge=1, le=50, description="Number of recent bids to return"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get recent bids with role-based filtering."""
    return bid_service.get_recent_bids(
        db, current_user.id,
        current_user.role, limit, current_user.team_id
    )


@router.get("/bids/winning", response_model=PaginatedResponse[BidResponse])
async def get_winning_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get winning bids with role-based filtering."""
    return bid_service.get_winning_bids(
        db, current_user.id,current_user.role, skip, limit, 
         current_user.team_id
    )


@router.get("/bids/my-bids", response_model=PaginatedResponse[BidResponse])
async def get_my_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    status_filter: Optional[BidStatus] = Query(None, alias="status", description="Filter by bid status"),
    vertical_id: Optional[str] = Query(None, description="Filter by vertical ID"),
    date_from: Optional[datetime] = Query(None, description="Filter bids from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter bids until this date"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-submitted_at", description="Sort field and direction"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get current user's bids (convenience endpoint for members)."""
    filters = BidListFilter(
        status=status_filter,
        vertical_id=UUID(vertical_id) if vertical_id else None,
        date_from=date_from,
        date_to=date_to
    )
    
    return bid_service.get_my_bids(
        db, filters, current_user.id, skip, limit, sort
    )


# =====================================================================
# CORE CRUD ENDPOINTS
# =====================================================================

@router.post("/bids", response_model=BidResponse)
async def create_bid(
    bid_data: BidCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Create a new bid with validation and permission checks."""
    return bid_service.create_bid(
        db, bid_data, current_user.id,
        current_user.role, current_user.team_id
    )

@router.get("/bids", response_model=PaginatedResponse[BidResponse])
async def get_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    status_filter: Optional[BidStatus] = Query(None, alias="status", description="Filter by bid status"),
    team_id: Optional[str] = Query(None, description="Filter by team ID (Admin/Sub-Admin only)"),
    member_id: Optional[str] = Query(None, description="Filter by member ID (Admin/Sub-Admin only)"),
    vertical_id: Optional[str] = Query(None, description="Filter by vertical ID"),
    budget_type: Optional[BudgetType] = Query(None, description="Filter by budget type"),
    date_from: Optional[datetime] = Query(None, description="Filter bids from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter bids until this date"),
    q: Optional[str] = Query(None, description="Search in job title, client name, proposal"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-submitted_at", description="Sort field and direction"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get bids with filtering and pagination."""
    filters = BidListFilter(
        status=status_filter,
        team_id=UUID(team_id) if team_id else None,
        member_id=UUID(member_id) if member_id else None,
        vertical_id=UUID(vertical_id) if vertical_id else None,
        budget_type=budget_type,
        date_from=date_from,
        date_to=date_to,
        q=q
    )
    
    return bid_service.get_bids(
        db, filters, current_user.id, current_user.role, 
        skip, limit, sort, current_user.team_id
    )


@router.get("/bids/{bid_id}", response_model=BidResponse)
async def get_bid(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Get bid by ID with role-based access control."""
    try:
        bid_uuid = UUID(bid_id)
        bid = bid_service.get_bid(
            db, bid_uuid, current_user.id,
            current_user.role, current_user.team_id
        )
        
        if not bid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bid not found"
            )
        
        return bid
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


@router.put("/bids/{bid_id}", response_model=BidResponse)
async def update_bid(
    bid_id: str,
    bid_data: BidUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Update bid with role-based permissions."""
    try:
        bid_uuid = UUID(bid_id)
        bid = bid_service.update_bid(
            db, bid_uuid, bid_data, current_user.id,
            current_user.role, current_user.team_id
        )
        
        if not bid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bid not found or cannot be updated"
            )
        
        return bid
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


@router.patch("/bids/{bid_id}/status", response_model=BidResponse)
async def update_bid_status(
    bid_id: str,
    status_data: BidStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Update bid status with role-based permissions."""
    try:
        bid_uuid = UUID(bid_id)
        bid = bid_service.update_bid_status(
            db, bid_uuid, status_data, current_user.id,
            current_user.role, current_user.team_id
        )
        
        if not bid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bid not found or status cannot be updated"
            )
        
        return bid
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


@router.delete("/bids/{bid_id}", response_model=SuccessResponse)
async def delete_bid(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Delete bid with role-based permissions."""
    try:
        bid_uuid = UUID(bid_id)
        return bid_service.delete_bid(
            db, bid_uuid, current_user.id,
            current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


# =====================================================================
# ANALYTICS / DASHBOARD
# =====================================================================

@router.get("/members/rankings", response_model=PaginatedResponse[MemberBidRanking])
async def get_member_rankings(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    vertical_id: Optional[str] = Query(None, description="Filter by vertical ID"),
    date_from: Optional[datetime] = Query(None, description="Filter from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter until this date"),
    min_bids: Optional[int] = Query(None, ge=0, description="Minimum number of bids"),
    sort_field: BidSortField = Query(BidSortField.WIN_RATE, description="Sort field"),
    sort_direction: SortDirection = Query(SortDirection.DESC, description="Sort direction"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get member bid rankings/leaderboard."""
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Members cannot access member rankings"
        )
    
    try:
        filters = MemberRankingFilter(
            team_id=UUID(team_id) if team_id else None,
            vertical_id=UUID(vertical_id) if vertical_id else None,
            date_from=date_from,
            date_to=date_to,
            min_bids=min_bids,
            sort_field=sort_field,
            sort_direction=sort_direction
        )
        
        return bid_service.get_member_rankings(
            db, filters, current_user.role, current_user.team_id, skip, limit
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.get("/earnings", response_model=EarningsResponse)
async def get_earnings(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    member_id: Optional[str] = Query(None, description="Filter by member ID"),
    vertical_id: Optional[str] = Query(None, description="Filter by vertical ID"),
    date_from: Optional[datetime] = Query(None, description="Filter from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter until this date"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get earnings data with breakdown by vertical, team, and member."""
    try:
        team_uuid = UUID(team_id) if team_id else None
        member_uuid = UUID(member_id) if member_id else None
        vertical_uuid = UUID(vertical_id) if vertical_id else None
        
        return bid_service.get_earnings(
            db, team_uuid, member_uuid, vertical_uuid,
            current_user.role, current_user.team_id, date_from, date_to
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.get("/analytics", response_model=BidAnalytics)
async def get_bid_analytics(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    member_id: Optional[str] = Query(None, description="Filter by member ID"),
    date_from: Optional[datetime] = Query(None, description="Filter from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter until this date"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get advanced bid analytics including trends and performance metrics."""
    try:
        team_uuid = UUID(team_id) if team_id else None
        member_uuid = UUID(member_id) if member_id else None
        
        return bid_service.get_bid_analytics(
            db, team_uuid, member_uuid, current_user.role,
            current_user.team_id, date_from, date_to
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.get("/trends/monthly", response_model=List[MonthlyTrend])
async def get_monthly_trends(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    member_id: Optional[str] = Query(None, description="Filter by member ID"),
    months: int = Query(12, ge=1, le=24, description="Number of months to include"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get monthly bid trends for the specified period."""
    try:
        team_uuid = UUID(team_id) if team_id else None
        member_uuid = UUID(member_id) if member_id else None
        
        return bid_service.get_monthly_trends(
            db, team_uuid, member_uuid, months,
            current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.get("/bid-summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Get bid summary for dashboard display."""
    return bid_service.get_dashboard_summary(
        db, current_user.id, current_user.role, current_user.team_id
    )


@router.get("/top-performers", response_model=List[MemberBidRanking])
async def get_top_performers(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    limit: int = Query(5, ge=1, le=20, description="Number of top performers to return"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get top performing members."""
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Members cannot access top performers list"
        )
    
    try:
        team_uuid = UUID(team_id) if team_id else None
        return bid_service.get_top_performers(
            db, team_uuid, limit, current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


# =====================================================================
# BULK OPERATIONS
# =====================================================================

@router.patch("/bids/bulk-status", response_model=List[BidResponse])
async def bulk_update_bid_status(
    bid_ids: List[str],
    status: BidStatus,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Bulk update bid status (Sub-Admin and Admin only)."""
    try:
        bid_uuids = [UUID(bid_id) for bid_id in bid_ids]
        return bid_service.bulk_update_status(
            db, bid_uuids, status, current_user.id,
            current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format in list"
        )


@router.delete("/bids/bulk", response_model=BulkOperationResult)
async def bulk_delete_bids(
    bid_ids: List[str],
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Bulk delete bids (Sub-Admin and Admin only)."""
    try:
        bid_uuids = [UUID(bid_id) for bid_id in bid_ids]
        return bid_service.bulk_delete_bids(
            db, bid_uuids, current_user.id,
            current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format in list"
        )


@router.patch("/bids/bulk-assign-team", response_model=BulkOperationResult)
async def bulk_assign_team(
    bid_ids: List[str],
    target_team_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Bulk assign bids to team (Admin only)."""
    try:
        bid_uuids = [UUID(bid_id) for bid_id in bid_ids]
        target_team_uuid = UUID(target_team_id)
        
        return bid_service.bulk_assign_team(
            db, bid_uuids, target_team_uuid, current_user.id,
            current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.post("/bids/bulk-operation", response_model=BulkOperationResult)
async def execute_bulk_operation(
    operation: BulkBidOperation,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Execute bulk operations on bids (Sub-Admin and Admin only)."""
    try:
        if operation.operation == "update_status":
            status = BidStatus(operation.data.get("status"))
            bid_responses = bid_service.bulk_update_status(
                db, operation.bid_ids, status, current_user.id,
                current_user.role, current_user.team_id
            )
            return BulkOperationResult(
                success_count=len(bid_responses),
                failed_count=len(operation.bid_ids) - len(bid_responses),
                total_count=len(operation.bid_ids)
            )
        elif operation.operation == "delete":
            return bid_service.bulk_delete_bids(
                db, operation.bid_ids, current_user.id,
                current_user.role, current_user.team_id
            )
        elif operation.operation == "assign_team":
            if current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can reassign teams"
                )
            target_team_id = UUID(operation.data.get("team_id"))
            return bid_service.bulk_assign_team(
                db, operation.bid_ids, target_team_id, current_user.id,
                current_user.role, current_user.team_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid bulk operation"
            )
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid operation data"
        )


# =====================================================================
# CONVENIENCE ENDPOINTS
# =====================================================================

@router.get("/bids/{bid_id}/can-edit", response_model=dict)
async def check_bid_edit_permission(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Check if current user can edit the specified bid."""
    try:
        bid_uuid = UUID(bid_id)
        return bid_service.check_bid_edit_permission(
            db, bid_uuid, current_user.id, current_user.role
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


@router.post("/calculate-costs", response_model=dict)
async def calculate_bid_costs(
    connects_used: int = Query(..., ge=1, le=50, description="Number of connects to use"),
    boost_connects: int = Query(0, ge=0, le=50, description="Number of boost connects to use"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Calculate bid costs for given connect usage."""
    return bid_service.calculate_bid_costs(connects_used, boost_connects)


# =====================================================================
# VERTICAL-SPECIFIC
# =====================================================================

@router.get("/verticals/{vertical_id}/bids", response_model=PaginatedResponse[BidResponse])
async def get_bids_by_vertical(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    status_filter: Optional[BidStatus] = Query(None, alias="status", description="Filter by bid status"),
    date_from: Optional[datetime] = Query(None, description="Filter bids from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter bids until this date"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-submitted_at", description="Sort field and direction"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get all bids for a specific vertical."""
    try:
        filters = BidListFilter(
            status=status_filter,
            vertical_id=UUID(vertical_id),
            date_from=date_from,
            date_to=date_to
        )
        
        return bid_service.get_bids(
            db, filters, current_user.id, current_user.role,
            skip, limit, sort, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


# =====================================================================
# TEAM-SPECIFIC
# =====================================================================

@router.get("/teams/{team_id}/bids", response_model=PaginatedResponse[BidResponse])
async def get_team_bids(
    team_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    status_filter: Optional[BidStatus] = Query(None, alias="status", description="Filter by bid status"),
    member_id: Optional[str] = Query(None, description="Filter by specific member"),
    date_from: Optional[datetime] = Query(None, description="Filter bids from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter bids until this date"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-submitted_at", description="Sort field and direction"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get all bids for a specific team."""
    try:
        team_uuid = UUID(team_id)
        
        # Sub-admins can only access their own team
        if current_user.role == UserRole.SUB_ADMIN and team_uuid != current_user.team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sub-admins can only access their own team's bids"
            )
        
        filters = BidListFilter(
            status=status_filter,
            team_id=team_uuid,
            member_id=UUID(member_id) if member_id else None,
            date_from=date_from,
            date_to=date_to
        )
        
        return bid_service.get_bids(
            db, filters, current_user.id, current_user.role,
            skip, limit, sort, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.get("/teams/{team_id}/statistics", response_model=TeamBidStats)
async def get_specific_team_statistics(
    team_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """Get detailed statistics for a specific team."""
    try:
        team_uuid = UUID(team_id)
        
        # Sub-admins can only access their own team
        if current_user.role == UserRole.SUB_ADMIN and team_uuid != current_user.team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sub-admins can only access their own team's statistics"
            )
        
        team_stats = bid_service.get_team_statistics(
            db, team_uuid, current_user.role, current_user.team_id
        )
        
        if not team_stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found or no statistics available"
            )
        
        return team_stats[0]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.get("/teams/{team_id}/earnings", response_model=EarningsResponse)
async def get_team_earnings(
    team_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    date_from: Optional[datetime] = Query(None, description="Filter from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter until this date"),
    bid_service: BidService = Depends(get_bid_service)
):
    """Get earnings for a specific team."""
    try:
        team_uuid = UUID(team_id)
        
        # Sub-admins can only access their own team
        if current_user.role == UserRole.SUB_ADMIN and team_uuid != current_user.team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sub-admins can only access their own team's earnings"
            )
        
        return bid_service.get_earnings(
            db, team_uuid, None, None, current_user.role,
            current_user.team_id, date_from, date_to
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )