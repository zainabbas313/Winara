from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.models import Team, TeamGoal, User
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

    @abstractmethod
    def get_team_members_count(self, db: Session, team_id: UUID) -> int:
        """
        Get count of active team members.
        
        Args:
            db: Database session
            team_id: ID of the team
            
        Returns:
            int: Number of active team members
        """
        pass

    @abstractmethod
    def get_team_members_detailed(self, db: Session, team_id: UUID) -> List[User]:
        """
        Get detailed team members with their statistics and relationships.
        
        Args:
            db: Database session
            team_id: ID of the team
            
        Returns:
            List[User]: List of team members with loaded relationships
        """
        pass

    @abstractmethod
    def validate_team_capacity(
        self, 
        db: Session, 
        team_id: UUID, 
        additional_users: int = 1
    ) -> bool:
        """
        Validate if team can accommodate additional users.
        
        Args:
            db: Database session
            team_id: ID of the team
            additional_users: Number of additional users to validate for
            
        Returns:
            bool: True if team has capacity, False otherwise
        """
        pass

    @abstractmethod
    def get_available_users_for_team(
        self, 
        db: Session, 
        limit: int = 100
    ) -> List[User]:
        """
        Get users who are not assigned to any team and can be added.
        
        Args:
            db: Database session
            limit: Maximum number of users to return
            
        Returns:
            List[User]: List of users available for team assignment
        """
        pass

    @abstractmethod
    def get_team_member_statistics(
        self, 
        db: Session, 
        team_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive team member statistics.
        
        Args:
            db: Database session
            team_id: ID of the team
            
        Returns:
            Dict containing member counts, role distribution, and performance metrics
        """
        pass

    @abstractmethod
    def update_team_member_statistics(self, db: Session, team_id: UUID) -> None:
        """
        Update statistics for all team members.
        
        Args:
            db: Database session
            team_id: ID of the team
            
        Returns:
            None
        """
        pass

    @abstractmethod
    def get_user_team_history(
        self, 
        db: Session, 
        user_id: UUID, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get team assignment history for a specific user.
        
        Args:
            db: Database session
            user_id: ID of the user
            limit: Maximum number of history records
            
        Returns:
            List of team assignment history records
        """
        pass

    @abstractmethod
    def get_team_assignment_conflicts(
        self, 
        db: Session, 
        user_ids: List[UUID], 
        team_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Check for conflicts when assigning users to a team.
        
        Args:
            db: Database session
            user_ids: List of user IDs to check
            team_id: Target team ID
            
        Returns:
            List of conflicts found (users already in teams, inactive users, etc.)
        """
        pass

    @abstractmethod
    def validate_team_member_removal(
        self, 
        db: Session, 
        team_id: UUID, 
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Validate if a team member can be safely removed.
        
        Args:
            db: Database session
            team_id: ID of the team
            user_id: ID of the user to remove
            
        Returns:
            Dict containing validation results and any blocking conditions
        """
        pass

    @abstractmethod
    def get_team_capacity_info(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        """
        Get team capacity information including current size and limits.
        
        Args:
            db: Database session
            team_id: ID of the team
            
        Returns:
            Dict containing capacity information
        """
        pass

    @abstractmethod
    def archive_team_membership_change(
        self, 
        db: Session, 
        team_id: UUID, 
        user_id: UUID, 
        action: str, 
        changed_by_id: UUID, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Archive a team membership change for audit purposes.
        
        Args:
            db: Database session
            team_id: ID of the team
            user_id: ID of the affected user
            action: Type of action (added, removed, role_changed)
            changed_by_id: ID of the user who made the change
            metadata: Additional metadata about the change
            
        Returns:
            None
        """
        pass