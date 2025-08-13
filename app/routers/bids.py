from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from dependencies.dependencies import (
    get_db, get_current_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentSubAdminUser
)
from services.bid_service import BidService
from schemas.bid import (
    BidCreate, BidUpdate, BidResponse, BidListFilter, 
    BidStatusUpdate, BidStats, BidSummary
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, BidStatus, BudgetType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_bid_service() -> BidService:
    return BidService()


@router.post("/bids", response_model=BidResponse)
async def create_bid(
    bid_data: BidCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Create a new bid.
    
    - **job_title**: Title of the job/project
    - **job_url**: URL to the job posting (optional)
    - **job_description**: Description of the job (optional)
    - **client_name**: Name of the client (optional)
    - **vertical_id**: ID of the assigned vertical
    - **member_id**: ID of the bidding member
    - **team_id**: ID of the member's team
    - **budget_type**: Type of budget (fixed or hourly)
    - **budget_min/max**: Budget range for fixed projects
    - **hourly_rate**: Rate for hourly projects
    - **estimated_hours**: Estimated hours for hourly projects
    - **connects_used**: Number of connects spent
    - **boost_connects_used**: Number of boost connects spent
    - **proposal_text**: Proposal content (optional)
    - **cover_letter**: Cover letter content (optional)
    - **competition_level**: Competition level (1-10)
    """
    return bid_service.create_bid(
        db, bid_data, current_user.id, 
        current_user.role, current_user.team_id
    )


@router.get("/bids", response_model=PaginatedResponse[BidResponse])
async def get_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    status: Optional[BidStatus] = Query(None, description="Filter by bid status"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    member_id: Optional[str] = Query(None, description="Filter by member ID"),
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
    """
    Get bids with filtering and pagination.
    
    Access control:
    - Admin: Can see all bids
    - Sub-Admin: Can see bids from their team
    - Member: Can see only their own bids
    """
    filters = BidListFilter(
        status=status,
        team_id=UUID(team_id) if team_id else None,
        member_id=UUID(member_id) if member_id else None,
        vertical_id=UUID(vertical_id) if vertical_id else None,
        budget_type=budget_type,
        date_from=date_from,
        date_to=date_to,
        q=q
    )
    
    return bid_service.get_bids(
        db, filters, skip, limit, sort,
        current_user.id, current_user.role, current_user.team_id
    )


@router.get("/bids/{bid_id}", response_model=BidResponse)
async def get_bid(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Get bid by ID.
    
    Access control:
    - Admin: Can see any bid
    - Sub-Admin: Can see bids from their team
    - Member: Can see only their own bids
    """
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
    """
    Update bid.
    
    Access control:
    - Admin: Can update any bid
    - Sub-Admin: Can update bids from their team (with approval after 5-day window)
    - Member: Can update their own bids (within 5-day window)
    """
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
    """
    Update bid status.
    
    Available status transitions:
    - not_viewed → viewed
    - viewed → declined/responded
    - responded → closed/won
    
    Access control:
    - Admin: Can update any bid status
    - Sub-Admin: Can update status for their team's bids
    - Member: Can update status for their own bids
    """
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
    """
    Delete bid.
    
    Access control:
    - Admin: Can delete any bid
    - Sub-Admin: Can delete bids from their team
    - Member: Can delete their own bids (within 5-day window)
    """
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


# Bulk operations
@router.patch("/bids/bulk-status", response_model=List[BidResponse])
async def bulk_update_bid_status(
    bid_ids: List[str],
    status: BidStatus,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Bulk update bid status (Sub-Admin and Admin only).
    
    - **bid_ids**: List of bid IDs to update
    - **status**: New status to apply to all bids
    """
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


# Statistics and analytics
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
    """
    Get bid statistics with role-based filtering.
    
    Returns:
    - Total bids count
    - Wins count
    - Win rate percentage
    - Total connects used
    - Total cost spent
    - Average response time
    """
    try:
        team_uuid = UUID(team_id) if team_id else None
        member_uuid = UUID(member_id) if member_id else None
        vertical_uuid = UUID(vertical_id) if vertical_id else None
        
        # Validate access based on role
        if current_user.role == UserRole.MEMBER:
            member_uuid = current_user.id  # Members can only see their own stats
        elif current_user.role == UserRole.SUB_ADMIN:
            team_uuid = current_user.team_id  # Sub-admins can only see their team stats
        
        return bid_service.get_bid_statistics(
            db, team_uuid, member_uuid, vertical_uuid,
            current_user.role, current_user.team_id
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )


@router.get("/bids/recent", response_model=List[BidResponse])
async def get_recent_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(10, ge=1, le=50, description="Number of recent bids to return"),
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Get recent bids with role-based filtering.
    """
    return bid_service.get_recent_bids(
        db, limit, current_user.id,
        current_user.role, current_user.team_id
    )


@router.get("/bids/winning", response_model=PaginatedResponse[BidResponse])
async def get_winning_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Get winning bids with role-based filtering.
    """
    return bid_service.get_winning_bids(
        db, skip, limit, current_user.id,
        current_user.role, current_user.team_id
    )


# Utility endpoints
@router.get("/bids/{bid_id}/can-edit", response_model=dict)
async def check_bid_edit_permission(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Check if current user can edit the specified bid.
    
    Returns information about edit permissions including:
    - can_edit: Boolean indicating if bid can be edited
    - reason: Reason if edit is not allowed
    - days_remaining: Days remaining in edit window (if applicable)
    """
    try:
        bid_uuid = UUID(bid_id)
        can_edit = bid_service.validate_bid_edit_permission(
            db, bid_uuid, current_user.id, current_user.role
        )
        
        return {
            "bid_id": bid_id,
            "can_edit": can_edit,
            "reason": "Within edit window" if can_edit else "Edit window expired or insufficient permissions"
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


@router.post("/bids/calculate-costs", response_model=dict)
async def calculate_bid_costs(
    connects_used: int = Query(..., ge=1, le=50, description="Number of connects to use"),
    boost_connects: int = Query(0, ge=0, le=50, description="Number of boost connects to use"),
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Calculate bid costs for given connect usage.
    
    Returns:
    - connect_cost: Cost of regular connects
    - boost_cost: Cost of boost connects
    - total_cost: Total cost
    """
    return bid_service.calculate_bid_costs(connects_used, boost_connects)


@router.get("/bids/my-bids", response_model=PaginatedResponse[BidResponse])
async def get_my_bids(
    current_user: CurrentUser,
    db: DatabaseSession,
    status: Optional[BidStatus] = Query(None, description="Filter by bid status"),
    vertical_id: Optional[str] = Query(None, description="Filter by vertical ID"),
    date_from: Optional[datetime] = Query(None, description="Filter bids from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter bids until this date"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-submitted_at", description="Sort field and direction"),
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Get current user's bids (convenience endpoint for members).
    """
    filters = BidListFilter(
        status=status,
        member_id=current_user.id,
        vertical_id=UUID(vertical_id) if vertical_id else None,
        date_from=date_from,
        date_to=date_to
    )
    
    return bid_service.get_bids(
        db, filters, skip, limit, sort,
        current_user.id, current_user.role, current_user.team_id
    )


@router.get("/bids/dashboard-summary", response_model=dict)
async def get_dashboard_summary(
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_service: BidService = Depends(get_bid_service)
):
    """
    Get bid summary for dashboard display.
    
    Returns summary statistics based on user role:
    - Admin: System-wide summary
    - Sub-Admin: Team summary
    - Member: Personal summary
    """
    team_id = None
    member_id = None
    
    if current_user.role == UserRole.MEMBER:
        member_id = current_user.id
    elif current_user.role == UserRole.SUB_ADMIN:
        team_id = current_user.team_id
    
    stats = bid_service.get_bid_statistics(
        db, team_id, member_id, None,
        current_user.role, current_user.team_id
    )
    
    recent_bids = bid_service.get_recent_bids(
        db, 5, current_user.id,
        current_user.role, current_user.team_id
    )
    
    return {
        "statistics": stats,
        "recent_bids": [BidSummary(
            id=bid.id,
            job_title=bid.job_title,
            status=bid.status,
            budget_type=bid.budget_type,
            connects_used=bid.connects_used,
            total_cost=bid.total_cost,
            submitted_at=bid.submitted_at,
            member_name=f"{bid.member.first_name} {bid.member.last_name}" if hasattr(bid, 'member') else "Unknown",
            vertical_name=bid.vertical.name if hasattr(bid, 'vertical') else "Unknown"
        ) for bid in recent_bids]
    }