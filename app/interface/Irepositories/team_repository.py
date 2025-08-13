from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.models import Team, TeamGoal
from schemas.team import TeamCreate, TeamUpdate, TeamListFilter, TeamGoalCreate, TeamGoalUpdate
from schemas.common import PaginatedResponse


class ITeamRepository(ABC):
    
    @abstractmethod
    def create(self, db: Session, team_data: TeamCreate, created_by_id: UUID) -> Team:
        """Create a new team."""
        pass
    
    @abstractmethod
    def get_by_id(self, db: Session, team_id: UUID) -> Optional[Team]:
        """Get team by ID."""
        pass
    
    @abstractmethod
    def get_by_name(self, db: Session, name: str) -> Optional[Team]:
        """Get team by name."""
        pass
    
    @abstractmethod
    def get_all(self, db: Session, filters: TeamListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get all teams with filters and pagination."""
        pass
    
    @abstractmethod
    def get_by_sub_admin(self, db: Session, sub_admin_id: UUID) -> Optional[Team]:
        """Get team managed by sub-admin."""
        pass
    
    @abstractmethod
    def update(self, db: Session, team_id: UUID, team_data: TeamUpdate) -> Optional[Team]:
        """Update team."""
        pass
    
    @abstractmethod
    def delete(self, db: Session, team_id: UUID) -> bool:
        """Delete team."""
        pass
    
    @abstractmethod
    def update_statistics(self, db: Session, team_id: UUID) -> None:
        """Update team statistics (total_earn, total_connect_used, total_bids)."""
        pass
    
    @abstractmethod
    def get_team_statistics(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        """Get team statistics."""
        pass
    
    @abstractmethod
    def get_team_performance(self, db: Session, team_id: UUID, 
                            days: int = 30) -> Dict[str, Any]:
        """Get team performance metrics."""
        pass
    
    # Team Goals
    @abstractmethod
    def create_goal(self, db: Session, team_id: UUID, goal_data: TeamGoalCreate, 
                   created_by_id: UUID) -> TeamGoal:
        """Create team goal."""
        pass
    
    @abstractmethod
    def get_goals(self, db: Session, team_id: UUID) -> List[TeamGoal]:
        """Get team goals."""
        pass
    
    @abstractmethod
    def get_goal_by_id(self, db: Session, goal_id: UUID) -> Optional[TeamGoal]:
        """Get team goal by ID."""
        pass
    
    @abstractmethod
    def update_goal(self, db: Session, goal_id: UUID, goal_data: TeamGoalUpdate) -> Optional[TeamGoal]:
        """Update team goal."""
        pass
    
    @abstractmethod
    def delete_goal(self, db: Session, goal_id: UUID) -> bool:
        """Delete team goal."""
        pass
    
    @abstractmethod
    def update_goal_progress(self, db: Session, team_id: UUID) -> None:
        """Update progress for all active team goals."""
        pass
    
    @abstractmethod
    def get_active_goals(self, db: Session, team_id: UUID) -> List[TeamGoal]:
        """Get active team goals."""
        pass