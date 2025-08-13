from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from dependencies.dependencies import (
    get_db, get_current_user, get_current_admin_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentAdminUser, CurrentSubAdminUser
)
from services.team_service import TeamService
from services.user_service import UserService
from schemas.team import (
    TeamCreate, TeamUpdate, TeamResponse, TeamListFilter, TeamSummary,
    TeamGoalCreate, TeamGoalUpdate, TeamGoalResponse, TeamMemberResponse
)
from schemas.user import UserResponse
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, UserStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_team_service() -> TeamService:
    return TeamService()

def get_user_service() -> UserService:
    return UserService()


# Admin-only endpoints
@router.post("/teams", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Create a new team (Admin only).
    
    - **name**: Unique team name
    - **description**: Optional team description
    - **sub_admin_id**: User ID to assign as sub-admin for this team
    - **status**: Team status (active, inactive, suspended)
    """
    return team_service.create_team(db, team_data, current_user.id)


@router.get("/teams", response_model=PaginatedResponse[TeamResponse])
async def get_teams(
    current_user: CurrentUser,
    db: DatabaseSession,
    status: Optional[UserStatus] = Query(None, description="Filter by team status"),
    sub_admin_id: Optional[str] = Query(None, description="Filter by sub-admin ID"),
    q: Optional[str] = Query(None, description="Search in team name and description"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-created_at", description="Sort field and direction"),
    team_service: TeamService = Depends(get_team_service)
):
    """
    Get teams with filtering and pagination.
    
    Access control:
    - Admin: Can see all teams
    - Sub-Admin: Can see only their own team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    filters = TeamListFilter(
        status=status,
        sub_admin_id=UUID(sub_admin_id) if sub_admin_id else None,
        q=q
    )
    
    return team_service.get_teams(
        db, filters,
        current_user.id, current_user.role.value, skip, limit, sort, current_user.team_id
    )


@router.get("/teams/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Get team by ID.
    
    Access control:
    - Admin: Can see any team
    - Sub-Admin: Can see only their own team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id)
        team = team_service.get_team(
            db, team_uuid, current_user.id, 
            current_user.role.value, current_user.team_id
        )
        
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )
        
        return team
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.put("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    team_data: TeamUpdate,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Update team (Admin only).
    """
    try:
        team_uuid = UUID(team_id)
        team = team_service.update_team(db, team_uuid, team_data, current_user.id)
        
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )
        
        return team
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.delete("/teams/{team_id}", response_model=SuccessResponse)
async def delete_team(
    team_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Delete team (Admin only).
    
    Note: Cannot delete teams that have members.
    """
    try:
        team_uuid = UUID(team_id)
        return team_service.delete_team(db, team_uuid, current_user.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


# Team members management
@router.get("/teams/{team_id}/members", response_model=List[TeamMemberResponse])
async def get_team_members(
    team_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    user_service: UserService = Depends(get_user_service)
):
    """
    Get team members.
    
    Access control:
    - Admin: Can see members of any team
    - Sub-Admin: Can see members of their own team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only access your own team members"
            )
        
        members = user_service.get_team_members(
            db, team_uuid, current_user.id, 
            current_user.role.value, current_user.team_id
        )
        
        # Convert to team member response format
        team_members = []
        for member in members:
            team_member = TeamMemberResponse(
                id=member.id,
                username=member.username,
                first_name=member.first_name,
                last_name=member.last_name,
                email=member.email,
                role=member.role.value,
                status=member.status.value,
                is_active=member.is_active,
                last_activity=member.last_activity
            )
            team_members.append(team_member)
        
        return team_members
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


# Team goals management
@router.get("/teams/{team_id}/goals", response_model=List[TeamGoalResponse])
async def get_team_goals(
    team_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Get team goals.
    
    Access control:
    - Admin: Can see goals for any team
    - Sub-Admin: Can see goals for their own team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only access your own team goals"
            )
        
        return team_service.get_team_goals(db, team_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.post("/teams/{team_id}/goals", response_model=TeamGoalResponse)
async def create_team_goal(
    team_id: str,
    goal_data: TeamGoalCreate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Create team goal (Sub-Admin and Admin only).
    
    - **goal_name**: Descriptive name for the goal
    - **goal_type**: Type of goal (bids, wins, revenue, win_rate)
    - **target_value**: Target value to achieve
    - **unit**: Unit of measurement
    - **period_start**: Goal period start date
    - **period_end**: Goal period end date
    """
    try:
        team_uuid = UUID(team_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only create goals for your own team"
            )
        
        return team_service.create_team_goal(
            db, team_uuid, goal_data, current_user.id
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.put("/teams/{team_id}/goals/{goal_id}", response_model=TeamGoalResponse)
async def update_team_goal(
    team_id: str,
    goal_id: str,
    goal_data: TeamGoalUpdate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Update team goal (Sub-Admin and Admin only).
    """
    try:
        team_uuid = UUID(team_id)
        goal_uuid = UUID(goal_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only update goals for your own team"
            )
        
        goal = team_service.update_team_goal(db, goal_uuid, goal_data)
        
        if not goal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team goal not found"
            )
        
        return goal
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )


@router.delete("/teams/{team_id}/goals/{goal_id}", response_model=SuccessResponse)
async def delete_team_goal(
    team_id: str,
    goal_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Delete team goal (Sub-Admin and Admin only).
    """
    try:
        team_uuid = UUID(team_id)
        goal_uuid = UUID(goal_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only delete goals for your own team"
            )
        
        return team_service.delete_team_goal(db, goal_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )


# Team statistics and performance
@router.get("/teams/{team_id}/statistics", response_model=dict)
async def get_team_statistics(
    team_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Get team statistics and performance metrics.
    
    Access control:
    - Admin: Can see statistics for any team
    - Sub-Admin: Can see statistics for their own team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only access your own team statistics"
            )
        
        return team_service.get_team_statistics(db, team_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.get("/teams/{team_id}/performance", response_model=dict)
async def get_team_performance(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days for performance analysis"),
    team_service: TeamService = Depends(get_team_service)
):
    """
    Get team performance trends over specified period.
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only access your own team performance"
            )
        
        return team_service.get_team_performance(db, team_uuid, days)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


# Utility endpoints
@router.post("/teams/{team_id}/update-statistics", response_model=SuccessResponse)
async def update_team_statistics(
    team_id: str,
    current_user: CurrentAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Manually update team statistics (Admin only).
    
    This endpoint recalculates all team statistics from current data.
    """
    try:
        team_uuid = UUID(team_id)
        team_service.update_team_statistics(db, team_uuid)
        return SuccessResponse(message="Team statistics updated successfully")
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.post("/teams/{team_id}/update-goal-progress", response_model=SuccessResponse)
async def update_goal_progress(
    team_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    team_service: TeamService = Depends(get_team_service)
):
    """
    Update progress for all active team goals (Sub-Admin and Admin only).
    """
    try:
        team_uuid = UUID(team_id)
        
        # Validate access
        if (current_user.role == UserRole.SUB_ADMIN and 
            current_user.team_id != team_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only update goals for your own team"
            )
        
        team_service.update_goal_progress(db, team_uuid)
        return SuccessResponse(message="Goal progress updated successfully")
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )