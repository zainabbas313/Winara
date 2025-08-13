from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from interface.Iservices.team_service import ITeamService
from repositories.team_repository import TeamRepository
from repositories.audit_repository import AuditRepository
from schemas.team import (
    TeamCreate, TeamUpdate, TeamResponse, TeamListFilter,
    TeamGoalCreate, TeamGoalUpdate, TeamGoalResponse
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, AuditAction
import logging

logger = logging.getLogger(__name__)


class TeamService(ITeamService):
    def __init__(self):
        self.team_repo = TeamRepository()
        self.audit_repo = AuditRepository()

    def create_team(self, db: Session, team_data: TeamCreate, created_by_id: UUID) -> TeamResponse:
        """Create a new team."""
        try:
            # Check if team name already exists
            existing_team = self.team_repo.get_by_name(db, team_data.name)
            if existing_team:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Team name already exists"
                )
            
            # Validate sub-admin exists and is available
            from repositories.user_repository import UserRepository
            user_repo = UserRepository()
            sub_admin = user_repo.get_by_id(db, team_data.sub_admin_id)
            
            if not sub_admin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sub-admin user not found"
                )
            
            if sub_admin.role != UserRole.SUB_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user must have sub-admin role"
                )
            
            # Check if sub-admin is already managing another team
            existing_team = self.team_repo.get_by_sub_admin(db, team_data.sub_admin_id)
            if existing_team:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sub-admin is already managing another team"
                )
            
            # Create team
            team = self.team_repo.create(db, team_data, created_by_id)
            
            # Update sub-admin's team assignment
            from schemas.user import UserUpdate
            user_update = UserUpdate(team_id=team.id)
            user_repo.update(db, team_data.sub_admin_id, user_update)
            
            # Log team creation
            self.audit_repo.create_audit_log(
                db, AuditAction.CREATE, "team", team.id, created_by_id, None,
                None, None, f"Team created: {team.name}",
                new_values={
                    "name": team.name,
                    "sub_admin_id": str(team.sub_admin_id),
                    "status": team.status.value
                }
            )
            
            return TeamResponse.from_orm(team)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating team: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Team creation failed"
            )

    def get_team(self, db: Session, team_id: UUID, requesting_user_id: UUID,
                requesting_user_role: str, requesting_user_team_id: Optional[UUID] = None) -> Optional[TeamResponse]:
        """Get team by ID with role-based access control."""
        try:
            team = self.team_repo.get_by_id(db, team_id)
            if not team:
                return None
            
            # Validate access
            if not self._validate_team_access(requesting_user_role, requesting_user_team_id, team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view this team"
                )
            
            return TeamResponse.from_orm(team)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting team {team_id}: {e}")
            return None

    def get_teams(self, db: Session, filters: TeamListFilter,
                 requesting_user_id: UUID, requesting_user_role: str,  skip: int = 0,
                 limit: int = 20, sort_by: str = "-created_at",
                 requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[TeamResponse]:
        """Get teams with filters and role-based access control."""
        try:
            # Apply role-based filtering
            if requesting_user_role == UserRole.SUB_ADMIN.value:
                # Sub-admins can only see their own team
                if requesting_user_team_id:
                    filters.sub_admin_id = None  # Clear any existing filter
                    # We'll filter the results after retrieval
                
            # Get teams
            result = self.team_repo.get_all(db, filters, skip, limit, sort_by)
            
            # Apply additional filtering for sub-admins
            if requesting_user_role == UserRole.SUB_ADMIN.value:
                filtered_items = [
                    team for team in result.items 
                    if team.id == requesting_user_team_id
                ]
                result.items = filtered_items
                result.count = len(filtered_items)
            
            # Convert to response objects
            team_responses = [TeamResponse.from_orm(team) for team in result.items]
            
            return PaginatedResponse(
                items=team_responses,
                next_cursor=result.next_cursor,
                count=result.count
            )
            
        except Exception as e:
            logger.error(f"Error getting teams: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def update_team(self, db: Session, team_id: UUID, team_data: TeamUpdate,
                   requesting_user_id: UUID) -> Optional[TeamResponse]:
        """Update team."""
        try:
            team = self.team_repo.get_by_id(db, team_id)
            if not team:
                return None
            
            # Store old values for audit
            old_values = {
                "name": team.name,
                "description": team.description,
                "sub_admin_id": str(team.sub_admin_id),
                "status": team.status.value
            }
            
            # If sub-admin is being changed, validate the new one
            if team_data.sub_admin_id and team_data.sub_admin_id != team.sub_admin_id:
                from repositories.user_repository import UserRepository
                user_repo = UserRepository()
                
                new_sub_admin = user_repo.get_by_id(db, team_data.sub_admin_id)
                if not new_sub_admin or new_sub_admin.role != UserRole.SUB_ADMIN:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid sub-admin user"
                    )
                
                # Check if new sub-admin is available
                existing_team = self.team_repo.get_by_sub_admin(db, team_data.sub_admin_id)
                if existing_team and existing_team.id != team_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Sub-admin is already managing another team"
                    )
                
                # Update old sub-admin's team assignment
                if team.sub_admin_id:
                    from schemas.user import UserUpdate
                    user_update = UserUpdate(team_id=None)
                    user_repo.update(db, team.sub_admin_id, user_update)
                
                # Update new sub-admin's team assignment
                user_update = UserUpdate(team_id=team_id)
                user_repo.update(db, team_data.sub_admin_id, user_update)
            
            # Update team
            updated_team = self.team_repo.update(db, team_id, team_data)
            if not updated_team:
                return None
            
            # Create new values for audit
            new_values = {
                "name": updated_team.name,
                "description": updated_team.description,
                "sub_admin_id": str(updated_team.sub_admin_id),
                "status": updated_team.status.value
            }
            
            # Log team update
            self.audit_repo.create_audit_log(
                db, AuditAction.UPDATE, "team", team_id, requesting_user_id, None,
                None, None, f"Team updated: {updated_team.name}",
                old_values=old_values,
                new_values=new_values
            )
            
            return TeamResponse.from_orm(updated_team)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating team {team_id}: {e}")
            return None

    def delete_team(self, db: Session, team_id: UUID, requesting_user_id: UUID) -> SuccessResponse:
        """Delete team."""
        try:
            team = self.team_repo.get_by_id(db, team_id)
            if not team:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Team not found"
                )
            
            # Store team info for audit
            team_info = {
                "name": team.name,
                "sub_admin_id": str(team.sub_admin_id),
                "status": team.status.value
            }
            
            # Delete team
            success = self.team_repo.delete(db, team_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete team with existing members"
                )
            
            # Update sub-admin's team assignment
            if team.sub_admin_id:
                from repositories.user_repository import UserRepository
                from schemas.user import UserUpdate
                user_repo = UserRepository()
                user_update = UserUpdate(team_id=None)
                user_repo.update(db, team.sub_admin_id, user_update)
            
            # Log team deletion
            self.audit_repo.create_audit_log(
                db, AuditAction.DELETE, "team", team_id, requesting_user_id, None,
                None, None, f"Team deleted: {team_info['name']}",
                old_values=team_info
            )
            
            return SuccessResponse(message="Team deleted successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting team {team_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Team deletion failed"
            )

    def update_team_statistics(self, db: Session, team_id: UUID) -> None:
        """Update team statistics."""
        try:
            self.team_repo.update_statistics(db, team_id)
        except Exception as e:
            logger.error(f"Error updating team statistics for {team_id}: {e}")

    def get_team_statistics(self, db: Session, team_id: UUID) -> dict:
        """Get team statistics."""
        try:
            return self.team_repo.get_team_statistics(db, team_id)
        except Exception as e:
            logger.error(f"Error getting team statistics for {team_id}: {e}")
            return {}

    def get_team_performance(self, db: Session, team_id: UUID, days: int = 30) -> dict:
        """Get team performance metrics."""
        try:
            return self.team_repo.get_team_performance(db, team_id, days)
        except Exception as e:
            logger.error(f"Error getting team performance for {team_id}: {e}")
            return {}

    # Team Goals
    def create_team_goal(self, db: Session, team_id: UUID, goal_data: TeamGoalCreate,
                        created_by_id: UUID) -> TeamGoalResponse:
        """Create team goal."""
        try:
            # Validate team exists
            team = self.team_repo.get_by_id(db, team_id)
            if not team:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Team not found"
                )
            
            # Create goal
            goal = self.team_repo.create_goal(db, team_id, goal_data, created_by_id)
            
            # Log goal creation
            self.audit_repo.create_audit_log(
                db, AuditAction.CREATE, "team_goal", goal.id, created_by_id, None,
                None, None, f"Team goal created: {goal.goal_name}",
                new_values={
                    "team_id": str(team_id),
                    "goal_name": goal.goal_name,
                    "goal_type": goal.goal_type,
                    "target_value": str(goal.target_value)
                }
            )
            
            return TeamGoalResponse.from_orm(goal)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating team goal: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Team goal creation failed"
            )

    def get_team_goals(self, db: Session, team_id: UUID) -> List[TeamGoalResponse]:
        """Get team goals."""
        try:
            goals = self.team_repo.get_goals(db, team_id)
            return [TeamGoalResponse.from_orm(goal) for goal in goals]
        except Exception as e:
            logger.error(f"Error getting team goals for {team_id}: {e}")
            return []

    def update_team_goal(self, db: Session, goal_id: UUID, goal_data: TeamGoalUpdate) -> Optional[TeamGoalResponse]:
        """Update team goal."""
        try:
            goal = self.team_repo.get_goal_by_id(db, goal_id)
            if not goal:
                return None
            
            # Store old values for audit
            old_values = {
                "goal_name": goal.goal_name,
                "target_value": str(goal.target_value),
                "is_active": goal.is_active,
                "is_achieved": goal.is_achieved
            }
            
            # Update goal
            updated_goal = self.team_repo.update_goal(db, goal_id, goal_data)
            if not updated_goal:
                return None
            
            # Create new values for audit
            new_values = {
                "goal_name": updated_goal.goal_name,
                "target_value": str(updated_goal.target_value),
                "is_active": updated_goal.is_active,
                "is_achieved": updated_goal.is_achieved
            }
            
            # Log goal update
            self.audit_repo.create_audit_log(
                db, AuditAction.UPDATE, "team_goal", goal_id, None, None,
                None, None, f"Team goal updated: {updated_goal.goal_name}",
                old_values=old_values,
                new_values=new_values
            )
            
            return TeamGoalResponse.from_orm(updated_goal)
            
        except Exception as e:
            logger.error(f"Error updating team goal {goal_id}: {e}")
            return None

    def delete_team_goal(self, db: Session, goal_id: UUID) -> SuccessResponse:
        """Delete team goal."""
        try:
            goal = self.team_repo.get_goal_by_id(db, goal_id)
            if not goal:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Team goal not found"
                )
            
            # Store goal info for audit
            goal_info = {
                "goal_name": goal.goal_name,
                "team_id": str(goal.team_id),
                "goal_type": goal.goal_type
            }
            
            # Delete goal
            success = self.team_repo.delete_goal(db, goal_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Team goal deletion failed"
                )
            
            # Log goal deletion
            self.audit_repo.create_audit_log(
                db, AuditAction.DELETE, "team_goal", goal_id, None, None,
                None, None, f"Team goal deleted: {goal_info['goal_name']}",
                old_values=goal_info
            )
            
            return SuccessResponse(message="Team goal deleted successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting team goal {goal_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Team goal deletion failed"
            )

    def update_goal_progress(self, db: Session, team_id: UUID) -> None:
        """Update progress for all active team goals."""
        try:
            self.team_repo.update_goal_progress(db, team_id)
        except Exception as e:
            logger.error(f"Error updating goal progress for team {team_id}: {e}")

    # Private helper methods
    def _validate_team_access(self, requesting_user_role: str, 
                             requesting_user_team_id: Optional[UUID], 
                             target_team_id: UUID) -> bool:
        """Validate if user has access to team data."""
        # Admin can access any team
        if requesting_user_role == UserRole.ADMIN.value:
            return True
        
        # Sub-admin can access their own team
        if requesting_user_role == UserRole.SUB_ADMIN.value:
            return requesting_user_team_id == target_team_id
        
        # Members cannot access team management
        return False