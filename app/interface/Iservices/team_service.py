from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.team import (
    TeamCreate, TeamUpdate, TeamResponse, TeamListFilter,
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
