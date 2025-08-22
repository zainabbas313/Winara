from fastapi import APIRouter, Depends, HTTPException, Path, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from dependencies.dependencies import (
    CurrentAdminOrSubAdminUser, get_db, get_current_user, get_current_admin_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentAdminUser, CurrentSubAdminUser,
    get_pagination_params
)
from services.user_service import UserService
from schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListFilter, UserSummary
)
from schemas.vertical import (
    VerticalUserAssignmentResponse, VerticalAssignmentFilter
)
from schemas.vertical import UserVerticalAssign, UserVerticalResponse
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, UserStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_user_service() -> UserService:
    return UserService()

#User endpoint
@router.get("/users/me", response_model=UserResponse)
async def get_user_info(
    current_user: CurrentUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user by ID.
    
    Access control:
    - Admin: Can see any user
    - Sub-Admin: Can see users in their team
    - Member: Can only see themselves
    """
    try:
        user = user_service.get_user_itself(
            db, current_user.id, current_user.id, 
            current_user.role.value, current_user.team_id
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

# Admin-only endpoints
@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Create a new user (Admin only).
    
    - **email**: Unique email address
    - **username**: Unique username
    - **password**: Password (will be hashed)
    - **first_name**: User's first name
    - **last_name**: User's last name
    - **role**: User role (admin, sub_admin, member)
    - **team_id**: Team assignment (optional)
    """
    return user_service.create_user(db, user_data, current_user.id)


@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def get_users(
    current_user: CurrentAdminOrSubAdminUser,
    db: DatabaseSession,
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    status: Optional[UserStatus] = Query(None, description="Filter by user status"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    q: Optional[str] = Query(None, description="Search in username, name, email"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-created_at", description="Sort field and direction"),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get users with filtering and pagination.
    
    Access control:
    - Admin: Can see all users
    - Sub-Admin: Can see users in their team
    - Member: Cannot access this endpoint
    """
    filters = UserListFilter(
        role=role,
        status=status,
        team_id=UUID(team_id) if team_id else None,
        q=q
    )
    
    return user_service.get_users(
        db, filters, 
        current_user.id, current_user.role.value,  skip, limit, sort, current_user.team_id
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user by ID.
    
    Access control:
    - Admin: Can see any user
    - Sub-Admin: Can see users in their team
    - Member: Can only see themselves
    """
    try:
        user_uuid = UUID(user_id)
        user = user_service.get_user(
            db, user_uuid, current_user.id, 
            current_user.role.value, current_user.team_id
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Update user.
    
    Access control:
    - Admin: Can update any user
    - Sub-Admin: Can update users in their team (limited fields)
    - Member: Can update themselves (limited fields)
    """
    try:
        user_uuid = UUID(user_id)
        user = user_service.update_user(
            db, user_uuid, user_data,
            current_user.id, current_user.role.value
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or insufficient permissions"
            )
        
        return user
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )


@router.delete("/users/{user_id}", response_model=SuccessResponse)
async def delete_user(
    user_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Delete user (Admin only).
    """
    try:
        user_uuid = UUID(user_id)
        return user_service.delete_user(
            db, user_uuid, current_user.id, current_user.role.value
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )


# Vertical assignment endpoints
@router.get("/users/me/verticals", response_model=List[UserVerticalResponse])
async def get_current_user_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service),
):
    """Get current user's assigned verticals."""
    return user_service.get_user_verticals(
        db, current_user.id, current_user.id, 
        current_user.role.value, current_user.team_id
    )

@router.get("/users/{user_id}/verticals", response_model=List[UserVerticalResponse])
async def get_user_verticals(
    current_user: CurrentUser,
    db: DatabaseSession,
    user_id: UUID = Path(..., description="User ID to get verticals for"),
    user_service: UserService = Depends(get_user_service),
):
    """
    Get user's assigned verticals.
    
    Access control:
    - Admin: Can see any user's verticals
    - Sub-Admin: Can see team members' verticals
    - Member: Can only see their own verticals
    """
    try:
        return user_service.get_user_verticals(
            db, user_id, current_user.id, 
            current_user.role.value, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )                                   
 
@router.post("/users/{user_id}/verticals", response_model=List[UserVerticalResponse])
async def assign_verticals_to_user(
    assignment_data: UserVerticalAssign,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Assign verticals to user (Sub-Admin and Admin only).
    
    - **vertical_ids**: List of vertical IDs to assign
    - **is_active**: Whether assignments are active
    - **notes**: Optional notes about the assignment
    """
    try:
        # Validate that vertical_ids are not empty
        if not assignment_data.vertical_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one vertical ID must be provided"
            )
        
        # Validate that vertical_ids are different from user_id
        if assignment_data.user_id in assignment_data.vertical_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID cannot be used as vertical ID"
            )
        
        return user_service.assign_verticals(
            db, assignment_data.user_id, assignment_data, current_user.id,
            current_user.role.value, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in assign_verticals_to_user endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/users/{user_id}/verticals/{vertical_id}", response_model=SuccessResponse)
async def remove_vertical_from_user(
    user_id: str,
    vertical_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Remove vertical assignment from user (Sub-Admin and Admin only).
    """
    try:
        user_uuid = UUID(user_id)
        vertical_uuid = UUID(vertical_id)
        return user_service.remove_vertical(
            db, user_uuid, vertical_uuid, current_user.id,
            current_user.role.value, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )


# NEW ENDPOINTS FOR VERTICAL USER ASSIGNMENTS
@router.get("/verticals/{vertical_id}/users", response_model=PaginatedResponse[VerticalUserAssignmentResponse])
async def get_vertical_assigned_users(
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_id: UUID = Path(..., description="Vertical ID to get assigned users for"),
    is_active: Optional[bool] = Query(None, description="Filter by assignment status"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    q: Optional[str] = Query(None, description="Search in user details"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get all users assigned to a specific vertical.
    
    Access control:
    - Admin: Can see all vertical assignments
    - Sub-Admin: Can see assignments for verticals where their team members are assigned
    - Member: Can only see assignments for verticals they are assigned to
    
    Returns a paginated list of users with their assignment details.
    """
    try:
        # Create filters
        filters = VerticalAssignmentFilter(
            is_active=is_active,
            role=role,
            team_id=UUID(team_id) if team_id else None,
            q=q
        )
        
        return user_service.get_vertical_assigned_users(
            db=db,
            vertical_id=vertical_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role.value,
            requesting_user_team_id=current_user.team_id,
            filters=filters,
            skip=skip,
            limit=limit
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter format: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting users for vertical {vertical_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving vertical assignments"
        )


@router.get("/verticals/{vertical_id}/users/{user_id}", response_model=VerticalUserAssignmentResponse)
async def get_vertical_user_assignment_details(
    current_user: CurrentUser,
    db: DatabaseSession,
    vertical_id: UUID = Path(..., description="Vertical ID"),
    user_id: UUID = Path(..., description="User ID"),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get detailed assignment information for a specific user-vertical combination.
    
    Access control:
    - Admin: Can see any assignment details
    - Sub-Admin: Can see assignment details for their team members
    - Member: Can only see their own assignment details
    
    Returns detailed information about the assignment including performance metrics.
    """
    try:
        assignment = user_service.get_vertical_user_assignment_details(
            db=db,
            vertical_id=vertical_id,
            user_id=user_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role.value,
            requesting_user_team_id=current_user.team_id
        )
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found or access denied"
            )
        
        return assignment
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assignment details for vertical {vertical_id} and user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving assignment details"
        )


# Utility endpoints
@router.get("/users/check-username/{username}", response_model=dict)
async def check_username_availability(
    username: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Check if username is available (Admin only).
    """
    available = user_service.check_username_availability(db, username)
    return {"available": available, "username": username}


@router.get("/users/check-email/{email}", response_model=dict)
async def check_email_availability(
    email: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Check if email is available (Admin only).
    """
    available = user_service.check_email_availability(db, email)
    return {"available": available, "email": email}


@router.post("/users/{user_id}/activate", response_model=SuccessResponse)
async def activate_user(
    user_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Activate user account (Admin only).
    """
    try:
        user_uuid = UUID(user_id)
        return user_service.activate_user(db, user_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )


@router.post("/users/{user_id}/deactivate", response_model=SuccessResponse)
async def deactivate_user(
    user_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Deactivate user account (Admin only).
    """
    try:
        user_uuid = UUID(user_id)
        return user_service.deactivate_user(db, user_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )