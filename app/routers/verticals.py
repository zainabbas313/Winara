from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from dependencies.dependencies import (
    get_db, get_current_user, get_current_admin_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentAdminUser, CurrentSubAdminUser
)
from services.vertical_service import VerticalService
from schemas.vertical import (
    VerticalCreate, VerticalUpdate, VerticalResponse, VerticalListFilter,
    VerticalSummary, VerticalStats
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_vertical_service() -> VerticalService:
    return VerticalService()


# Admin-only endpoints
@router.post("/verticals", response_model=VerticalResponse)
async def create_vertical(
    vertical_data: VerticalCreate,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Create a new vertical (Admin only).
    
    - **name**: Vertical name
    - **slug**: URL-friendly identifier
    - **description**: Optional description
    - **parent_id**: Parent vertical ID for hierarchical structure
    - **level**: Hierarchy level (0 for root)
    - **sort_order**: Display order
    - **is_active**: Whether vertical is active
    - **requires_approval**: Whether assignments require approval
    - **competition_level**: Competition level (1-10)
    """
    return vertical_service.create_vertical(db, vertical_data, current_user.id)


@router.get("/verticals", response_model=PaginatedResponse[VerticalResponse])
async def get_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    parent_id: Optional[str] = Query(None, description="Filter by parent vertical ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    q: Optional[str] = Query(None, description="Search in name, description, slug"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("sort_order", description="Sort field and direction"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get verticals with filtering and pagination.
    
    All users can view active verticals for assignment purposes.
    """
    filters = VerticalListFilter(
        parent_id=UUID(parent_id) if parent_id else None,
        is_active=is_active,
        q=q
    )
    
    return vertical_service.get_verticals(db, filters, skip, limit, sort)


@router.get("/verticals/{vertical_id}", response_model=VerticalResponse)
async def get_vertical(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get vertical by ID.
    """
    try:
        vertical_uuid = UUID(vertical_id)
        vertical = vertical_service.get_vertical(db, vertical_uuid)
        
        if not vertical:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vertical not found"
            )
        
        return vertical
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.put("/verticals/{vertical_id}", response_model=VerticalResponse)
async def update_vertical(
    vertical_id: str,
    vertical_data: VerticalUpdate,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Update vertical (Admin only).
    """
    try:
        vertical_uuid = UUID(vertical_id)
        vertical = vertical_service.update_vertical(db, vertical_uuid, vertical_data)
        
        if not vertical:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vertical not found"
            )
        
        return vertical
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.delete("/verticals/{vertical_id}", response_model=SuccessResponse)
async def delete_vertical(
    vertical_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Delete vertical (Admin only).
    
    Note: Cannot delete verticals that have children, assignments, or bids.
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.delete_vertical(db, vertical_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


# Hierarchy and navigation endpoints
@router.get("/verticals/{vertical_id}/children", response_model=List[VerticalResponse])
async def get_vertical_children(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get child verticals of a parent vertical.
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.get_children(db, vertical_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.get("/verticals/{vertical_id}/hierarchy", response_model=List[VerticalResponse])
async def get_vertical_hierarchy(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get full hierarchy path for a vertical (from root to current).
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.get_hierarchy(db, vertical_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.get("/verticals/root", response_model=List[VerticalResponse])
async def get_root_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get root level verticals (those with no parent).
    """
    return vertical_service.get_by_parent(db, None)


# Statistics and performance endpoints
@router.get("/verticals/{vertical_id}/statistics", response_model=dict)
async def get_vertical_statistics(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get vertical statistics and performance metrics.
    
    Access control:
    - Admin: Can see statistics for any vertical
    - Sub-Admin: Can see statistics for verticals assigned to their team members
    - Member: Can see statistics for their assigned verticals
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.get_statistics(
            db, vertical_uuid, current_user.id, 
            current_user.role.value, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.get("/verticals/{vertical_id}/performance", response_model=List[dict])
async def get_vertical_performance_trends(
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days for trend analysis"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get vertical performance trends over specified period.
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.get_performance_trends(db, vertical_uuid, days)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.get("/verticals/top-performing", response_model=List[VerticalResponse])
async def get_top_performing_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(10, ge=1, le=50, description="Number of top verticals to return"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get top performing verticals by success rate.
    """
    return vertical_service.get_top_performing(db, limit)


@router.get("/verticals/most-active", response_model=List[VerticalResponse])
async def get_most_active_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(10, ge=1, le=50, description="Number of verticals to return"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get most active verticals by bid count.
    """
    return vertical_service.get_most_active(db, limit)


# Search and utility endpoints
@router.get("/verticals/search", response_model=List[VerticalResponse])
async def search_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Search verticals by name, description, or slug.
    """
    return vertical_service.search(db, q, limit)


@router.get("/verticals/available-for-user/{user_id}", response_model=List[VerticalResponse])
async def get_available_verticals_for_user(
    user_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get verticals available for assignment to a user (Sub-Admin and Admin only).
    
    Returns verticals that are active and not already assigned to the user.
    """
    try:
        user_uuid = UUID(user_id)
        
        # Validate permission to assign verticals to this user
        if current_user.role == UserRole.SUB_ADMIN:
            # Sub-admin can only assign to their team members
            # This validation would be done in the service layer
            pass
        
        return vertical_service.get_available_for_assignment(db, user_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )


# Admin utility endpoints
@router.post("/verticals/{vertical_id}/update-statistics", response_model=SuccessResponse)
async def update_vertical_statistics(
    vertical_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Manually update vertical statistics (Admin only).
    
    Recalculates statistics from current bid data.
    """
    try:
        vertical_uuid = UUID(vertical_id)
        vertical_service.update_statistics(db, vertical_uuid)
        return SuccessResponse(message="Vertical statistics updated successfully")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.post("/verticals/{vertical_id}/update-sort-order", response_model=SuccessResponse)
async def update_vertical_sort_order(
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_id: str,
    new_order: int = Query(..., ge=0, description="New sort order"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Update vertical sort order (Admin only).
    """
    try:
        vertical_uuid = UUID(vertical_id)
        success = vertical_service.update_sort_order(db, vertical_uuid, new_order)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vertical not found"
            )
        
        return SuccessResponse(message="Sort order updated successfully")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )


@router.get("/verticals/statistics/summary", response_model=VerticalStats)
async def get_verticals_summary_statistics(
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get summary statistics for all verticals.
    """
    return vertical_service.get_summary_statistics(db)


# Bulk operations
@router.post("/verticals/bulk-activate", response_model=SuccessResponse)
async def bulk_activate_verticals(
    vertical_ids: List[str],
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Bulk activate verticals (Admin only).
    """
    try:
        vertical_uuids = [UUID(vid) for vid in vertical_ids]
        count = vertical_service.bulk_activate(db, vertical_uuids)
        return SuccessResponse(message=f"Activated {count} verticals successfully")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format in list"
        )


@router.post("/verticals/bulk-deactivate", response_model=SuccessResponse)
async def bulk_deactivate_verticals(
    vertical_ids: List[str],
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Bulk deactivate verticals (Admin only).
    """
    try:
        vertical_uuids = [UUID(vid) for vid in vertical_ids]
        count = vertical_service.bulk_deactivate(db, vertical_uuids)
        return SuccessResponse(message=f"Deactivated {count} verticals successfully")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format in list"
        )