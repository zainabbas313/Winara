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
    VerticalSummary, VerticalStats, BulkVerticalOperation
)

from schemas.common import SuccessResponse, VerticalPaginatedResponse
from models.models import UserRole
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verticals", tags=["Verticals"])

# Dependency injection
def get_vertical_service() -> VerticalService:
    return VerticalService()


# ==========================================
# CRUD OPERATIONS (Admin Only)
# ==========================================

@router.post("", response_model=VerticalResponse, status_code=status.HTTP_201_CREATED)
async def create_vertical(
    vertical_data: VerticalCreate,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Create a new vertical (Admin only).
    
    For root-level verticals (first time insert), set parent_id to null.
    For child verticals, provide the parent_id of an existing active vertical.
    
    **Request Body:**
    - **name**: Vertical name (required)
    - **slug**: URL-friendly identifier (required, will be auto-formatted)
    - **description**: Optional description
    - **parent_id**: Parent vertical ID (null for root level)
    - **sort_order**: Display order (default: 0)
    - **is_active**: Whether vertical is active (default: true)
    - **requires_approval**: Whether assignments require approval (default: false)
    - **competition_level**: Competition level 1-10 (default: 1)
    """
    try:
        return vertical_service.create_vertical(db, vertical_data, current_user.id)
    except Exception as e:
        logger.error(f"Error in create_vertical endpoint: {str(e)}")
        raise


# Fixed endpoint with proper default value handling
@router.get("", response_model=VerticalPaginatedResponse[VerticalResponse])
async def get_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    parent_id: Optional[str] = Query(
        default=None, 
        description="Filter by parent vertical ID (null for root level)"
    ),
    is_active: Optional[bool] = Query(
        default=None, 
        description="Filter by active status"
    ),
    q: Optional[str] = Query(
        default=None, 
        description="Search in name, description, slug"
    ),
    skip: int = Query(
        default=0, 
        ge=0, 
        description="Number of records to skip"
    ),
    limit: int = Query(
        default=20, 
        ge=1, 
        le=100, 
        description="Number of records to return"
    ),
    sort: str = Query(
        default="sort_order", 
        description="Sort field (prefix with - for desc)"
    ),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get verticals with filtering and pagination.
    
    **Query Parameters:**
    - **parent_id**: Filter by parent ID (use "null" for root level verticals)
    - **is_active**: Filter by active status (defaults to all if not specified)
    - **q**: Search term for name, description, or slug
    - **skip**: Number of records to skip for pagination (default: 0)
    - **limit**: Maximum number of records to return (default: 20, max: 100)
    - **sort**: Sort field, prefix with '-' for descending order (default: sort_order)
    """
    try:
        # Handle special case for root level verticals
        parsed_parent_id = None
        if parent_id is not None and parent_id.lower() != "null":
            try:
                parsed_parent_id = UUID(parent_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid parent_id format. Must be a valid UUID or 'null'."
                )
        
        # Ensure defaults are applied
        skip = max(0, skip)  # Ensure skip is never negative
        limit = max(1, min(100, limit))  # Ensure limit is between 1 and 100
        sort = sort.strip() if sort else "sort_order"  # Handle empty sort
        
        # Create filters with proper defaults
        filters = VerticalListFilter(
            parent_id=parsed_parent_id,
            is_active=is_active,  # None means no filter
            q=q.strip() if q else None  # Handle empty search string
        )
        
        # Get data from service
        result = vertical_service.get_verticals(db, filters, skip, limit, sort)
        
        # Ensure result has proper structure
        if not isinstance(result, VerticalPaginatedResponse):
            # If service returns raw data, wrap it properly
            items = getattr(result, 'items', [])
            total = getattr(result, 'total', len(items))
            
            return VerticalPaginatedResponse.create(
                items=items,
                total=total,
                skip=skip,
                limit=limit
            )
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error in get_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in get_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/{vertical_id}", response_model=VerticalResponse)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_vertical endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{vertical_id}", response_model=VerticalResponse)
async def update_vertical(
    vertical_id: str,
    vertical_data: VerticalUpdate,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Update vertical (Admin only).
    
    **Path Parameters:**
    - **vertical_id**: UUID of the vertical to update
    
    **Request Body:** All fields are optional for updates
    - **name**: Vertical name
    - **slug**: URL-friendly identifier
    - **description**: Description
    - **parent_id**: Parent vertical ID (null for root level)
    - **sort_order**: Display order
    - **is_active**: Whether vertical is active
    - **requires_approval**: Whether assignments require approval
    - **competition_level**: Competition level 1-10
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_vertical endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{vertical_id}", response_model=SuccessResponse)
async def delete_vertical(
    vertical_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Delete vertical (Admin only).
    
    **Note:** Cannot delete verticals that have:
    - Child verticals
    - Active user assignments  
    - Existing bids
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.delete_vertical(db, vertical_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_vertical endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ==========================================
# HIERARCHY AND NAVIGATION
# ==========================================

@router.get("/root/list", response_model=List[VerticalResponse])
async def get_root_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get root level verticals (those with no parent).
    
    This endpoint returns all top-level verticals that can serve as starting points
    for the vertical hierarchy.
    """
    try:
        return vertical_service.get_by_parent(db, None)
    except Exception as e:
        logger.error(f"Error in get_root_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{vertical_id}/children", response_model=List[VerticalResponse])
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_vertical_children endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{vertical_id}/hierarchy", response_model=List[VerticalResponse])
async def get_vertical_hierarchy(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get full hierarchy path for a vertical (from root to current).
    
    Returns the complete path from the root vertical down to the specified vertical,
    useful for breadcrumb navigation.
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.get_hierarchy(db, vertical_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_vertical_hierarchy endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ==========================================
# STATISTICS AND PERFORMANCE
# ==========================================

@router.get("/{vertical_id}/statistics", response_model=dict)
async def get_vertical_statistics(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get vertical statistics and performance metrics.
    
    **Access Control:**
    - **Admin**: Can see statistics for any vertical
    - **Sub-Admin**: Can see statistics for verticals assigned to their team members
    - **Member**: Can see statistics for their assigned verticals only
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_vertical_statistics endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{vertical_id}/performance", response_model=List[dict])
async def get_vertical_performance_trends(
    vertical_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    days: int = Query(30, ge=1, le=365, description="Number of days for trend analysis"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get vertical performance trends over specified period.
    
    Returns daily performance metrics including bid counts, earnings, 
    connects used, wins, and success rates.
    """
    try:
        vertical_uuid = UUID(vertical_id)
        return vertical_service.get_performance_trends(db, vertical_uuid, days)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vertical ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_vertical_performance_trends endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/analytics/top-performing", response_model=List[VerticalResponse])
async def get_top_performing_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(10, ge=1, le=50, description="Number of top verticals to return"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get top performing verticals by success rate.
    
    Returns verticals ordered by success rate and total earnings.
    """
    try:
        return vertical_service.get_top_performing(db, limit)
    except Exception as e:
        logger.error(f"Error in get_top_performing_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/analytics/most-active", response_model=List[VerticalResponse])
async def get_most_active_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(10, ge=1, le=50, description="Number of verticals to return"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get most active verticals by bid count.
    
    Returns verticals ordered by total number of bids and earnings.
    """
    try:
        return vertical_service.get_most_active(db, limit)
    except Exception as e:
        logger.error(f"Error in get_most_active_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/analytics/summary", response_model=VerticalStats)
async def get_verticals_summary_statistics(
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get summary statistics for all verticals.
    
    Returns aggregated metrics including total counts, earnings, 
    success rates, and distribution by hierarchy level.
    """
    try:
        return vertical_service.get_summary_statistics(db)
    except Exception as e:
        logger.error(f"Error in get_verticals_summary_statistics endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ==========================================
# SEARCH AND UTILITY
# ==========================================

@router.get("/search/query", response_model=List[VerticalResponse])
async def search_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Search verticals by name, description, or slug.
    
    **Query Parameters:**
    - **q**: Search term (minimum 1 character)
    - **limit**: Maximum number of results to return
    """
    try:
        return vertical_service.search(db, q, limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/assignments/available-for-user/{user_id}", response_model=List[VerticalResponse])
async def get_available_verticals_for_user(
    user_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Get verticals available for assignment to a user (Sub-Admin and Admin only).
    
    Returns verticals that are active and not already assigned to the specified user.
    Sub-admins can only query for users in their team.
    """
    try:
        user_uuid = UUID(user_id)
        
        # TODO: Add team validation for sub-admins
        # if current_user.role == UserRole.SUB_ADMIN:
        #     # Validate that user belongs to sub-admin's team
        #     pass
        
        return vertical_service.get_available_for_assignment(db, user_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_available_verticals_for_user endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ==========================================
# ADMIN UTILITY OPERATIONS
# ==========================================

@router.post("/{vertical_id}/update-statistics", response_model=SuccessResponse)
async def update_vertical_statistics(
    vertical_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Manually update vertical statistics (Admin only).
    
    Recalculates statistics from current bid data. Useful when data inconsistencies
    are detected or after bulk data operations.
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_vertical_statistics endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{vertical_id}/update-sort-order", response_model=SuccessResponse)
async def update_vertical_sort_order(
    vertical_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    new_order: int = Query(..., ge=0, description="New sort order"),
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Update vertical sort order (Admin only).
    
    Changes the display order of a vertical within its hierarchy level.
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_vertical_sort_order endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ==========================================
# BULK OPERATIONS
# ==========================================

@router.post("/bulk/activate", response_model=SuccessResponse)
async def bulk_activate_verticals(
    operation_data: BulkVerticalOperation,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Bulk activate verticals (Admin only).
    
    **Request Body:**
    - **vertical_ids**: List of vertical UUIDs to activate (1-100 items)
    """
    try:
        count = vertical_service.bulk_activate(db, operation_data.vertical_ids)
        return SuccessResponse(message=f"Successfully activated {count} verticals")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk_activate_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/bulk/deactivate", response_model=SuccessResponse)
async def bulk_deactivate_verticals(
    operation_data: BulkVerticalOperation,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    vertical_service: VerticalService = Depends(get_vertical_service)
):
    """
    Bulk deactivate verticals (Admin only).
    
    **Request Body:**
    - **vertical_ids**: List of vertical UUIDs to deactivate (1-100 items)
    """
    try:
        count = vertical_service.bulk_deactivate(db, operation_data.vertical_ids)
        return SuccessResponse(message=f"Successfully deactivated {count} verticals")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk_deactivate_verticals endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )