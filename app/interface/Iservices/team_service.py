from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.team import (
    AddUserToTeamRequest, BulkAddUsersRequest, BulkAddUsersResponse, TeamCreate, TeamMemberResponse, TeamUpdate, TeamResponse, TeamListFilter,
    TeamGoalCreate, TeamGoalUpdate, TeamGoalResponse
)
from schemas.common import SuccessResponse, PaginatedResponse


class ITeamService(ABC):
    """Interface for team-related operations."""

    @abstractmethod
    def create_team(self, db: Session, team_data: TeamCreate, created_by_id: UUID) -> TeamResponse:
        """Create a new team."""
        pass

    @abstractmethod
    def get_team(
        self, db: Session, team_id: UUID, requesting_user_id: UUID,
        requesting_user_role: str, requesting_user_team_id: Optional[UUID] = None
    ) -> Optional[TeamResponse]:
        """Get a team by ID with role-based access control."""
        pass

    @abstractmethod
    def get_teams(
        self, db: Session, filters: TeamListFilter,
        requesting_user_id: UUID, requesting_user_role: str,
        skip: int = 0, limit: int = 20, sort_by: str = "-created_at",
        requesting_user_team_id: Optional[UUID] = None
    ) -> PaginatedResponse[TeamResponse]:
        """Get multiple teams with filters and role-based access control."""
        pass

    @abstractmethod
    def update_team(self, db: Session, team_id: UUID, team_data: TeamUpdate,
                    requesting_user_id: UUID) -> Optional[TeamResponse]:
        """Update a team."""
        pass

    @abstractmethod
    def delete_team(self, db: Session, team_id: UUID, requesting_user_id: UUID) -> SuccessResponse:
        """Delete a team."""
        pass

    @abstractmethod
    def update_team_statistics(self, db: Session, team_id: UUID) -> None:
        """Update statistics for a team."""
        pass

    @abstractmethod
    def get_team_statistics(self, db: Session, team_id: UUID) -> dict:
        """Get team statistics."""
        pass

    @abstractmethod
    def get_team_performance(self, db: Session, team_id: UUID, days: int = 30) -> dict:
        """Get performance metrics for a team."""
        pass

    # Team Goals
    @abstractmethod
    def create_team_goal(self, db: Session, team_id: UUID, goal_data: TeamGoalCreate,
                         created_by_id: UUID) -> TeamGoalResponse:
        """Create a new goal for a team."""
        pass

    @abstractmethod
    def get_team_goals(self, db: Session, team_id: UUID) -> List[TeamGoalResponse]:
        """Get all goals for a team."""
        pass

    @abstractmethod
    def update_team_goal(self, db: Session, goal_id: UUID, goal_data: TeamGoalUpdate) -> Optional[TeamGoalResponse]:
        """Update a specific team goal."""
        pass

    @abstractmethod
    def delete_team_goal(self, db: Session, goal_id: UUID) -> SuccessResponse:
        """Delete a specific team goal."""
        pass

    @abstractmethod
    def update_goal_progress(self, db: Session, team_id: UUID) -> None:
        """Update progress for all active team goals."""
        pass

    @abstractmethod
    def add_user_to_team(
        self, 
        db: Session, 
        team_id: UUID, 
        user_data: AddUserToTeamRequest, 
        requesting_user_id: UUID
    ) -> TeamMemberResponse:
        """
        Add a user to a team.
        
        Args:
            db: Database session
            team_id: ID of the team to add user to
            user_data: User data including user_id and optional role
            requesting_user_id: ID of the user making the request
            
        Returns:
            TeamMemberResponse: Details of the added team member
            
        Raises:
            HTTPException: If validation fails or operation is not permitted
        """
        pass

    @abstractmethod
    def remove_user_from_team(
        self, 
        db: Session, 
        team_id: UUID, 
        user_id: UUID, 
        requesting_user_id: UUID
    ) -> SuccessResponse:
        """
        Remove a user from a team.
        
        Args:
            db: Database session
            team_id: ID of the team to remove user from
            user_id: ID of the user to remove
            requesting_user_id: ID of the user making the request
            
        Returns:
            SuccessResponse: Confirmation of successful removal
            
        Raises:
            HTTPException: If validation fails or operation is not permitted
        """
        pass

    @abstractmethod
    def bulk_add_users_to_team(
        self, 
        db: Session, 
        team_id: UUID, 
        users_data: BulkAddUsersRequest, 
        requesting_user_id: UUID
    ) -> BulkAddUsersResponse:
        """
        Add multiple users to a team in bulk.
        
        Args:
            db: Database session
            team_id: ID of the team to add users to
            users_data: Bulk request containing list of user IDs and default role
            requesting_user_id: ID of the user making the request
            
        Returns:
            BulkAddUsersResponse: Results of bulk operation including successes and failures
            
        Raises:
            HTTPException: If team not found or operation is not permitted
        """
        pass

    @abstractmethod
    def validate_user_team_assignment(
        self, 
        db: Session, 
        user_id: UUID, 
        team_id: UUID
    ) -> Dict[str, Any]:
        """
        Validate if a user can be assigned to a team.
        
        Args:
            db: Database session
            user_id: ID of the user to validate
            team_id: ID of the target team
            
        Returns:
            Dict containing validation results and any issues
        """
        pass

    @abstractmethod
    def get_team_membership_history(
        self, 
        db: Session, 
        team_id: UUID, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get history of team membership changes.
        
        Args:
            db: Database session
            team_id: ID of the team
            limit: Maximum number of history records to return
            
        Returns:
            List of membership change records
        """
        pass
