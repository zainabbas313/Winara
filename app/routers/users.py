from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from dependencies.dependencies import (
    get_db, get_current_user, get_current_admin_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentAdminUser, CurrentSubAdminUser,
    get_pagination_params
)
from services.user_service import UserService
from schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListFilter, UserSummary
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
    current_user: CurrentUser,
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
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    filters = UserListFilter(
        role=role,
        status=status,
        team_id=UUID(team_id) if team_id else None,
        q=q
    )
    
    return user_service.get_users(
        db, filters, skip, limit, sort,
        current_user.id, current_user.role.value, current_user.team_id
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
@router.get("/users/{user_id}/verticals", response_model=List[UserVerticalResponse])
async def get_user_verticals(
    user_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user's assigned verticals.
    
    Access control:
    - Admin: Can see any user's verticals
    - Sub-Admin: Can see team members' verticals
    - Member: Can only see their own verticals
    """
    try:
        user_uuid = UUID(user_id)
        return user_service.get_user_verticals(
            db, user_uuid, current_user.id, 
            current_user.role.value, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )


@router.post("/users/{user_id}/verticals", response_model=List[UserVerticalResponse])
async def assign_verticals_to_user(
    user_id: str,
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
        user_uuid = UUID(user_id)
        return user_service.assign_verticals(
            db, user_uuid, assignment_data, current_user.id,
            current_user.role.value, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
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