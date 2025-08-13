from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserUpdate, UserResponse, UserListFilter
from schemas.vertical import UserVerticalAssign, UserVerticalResponse
from schemas.common import SuccessResponse, PaginatedResponse


class IUserService(ABC):
    
    @abstractmethod
    def create_user(self, db: Session, user_data: UserCreate, created_by_id: UUID) -> UserResponse:
        """Create a new user."""
        pass
    
    @abstractmethod
    def get_user(self, db: Session, user_id: UUID, requesting_user_id: UUID,
                requesting_user_role: str) -> Optional[UserResponse]:
        """Get user by ID with role-based access control."""
        pass
    
    @abstractmethod
    def get_users(self, db: Session, filters: UserListFilter, 
                 requesting_user_id: UUID, requesting_user_role: str, skip: int = 0,
                 limit: int = 20, sort_by: str = "-created_at",
                 requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[UserResponse]:
        """Get users with filters and role-based access control."""
        pass
    
    @abstractmethod
    def update_user(self, db: Session, user_id: UUID, user_data: UserUpdate,
                   requesting_user_id: UUID, requesting_user_role: str) -> Optional[UserResponse]:
        """Update user with role-based access control."""
        pass
    
    @abstractmethod
    def delete_user(self, db: Session, user_id: UUID, requesting_user_id: UUID,
                   requesting_user_role: str) -> SuccessResponse:
        """Delete user with role-based access control."""
        pass
    
    @abstractmethod
    def get_user_verticals(self, db: Session, user_id: UUID,
                          requesting_user_id: UUID, requesting_user_role: str,
                          requesting_user_team_id: Optional[UUID] = None) -> List[UserVerticalResponse]:
        """Get user's assigned verticals."""
        pass
    
    @abstractmethod
    def assign_verticals(self, db: Session, user_id: UUID, assignment_data: UserVerticalAssign,
                        assigned_by_id: UUID, requesting_user_role: str,
                        requesting_user_team_id: Optional[UUID] = None) -> List[UserVerticalResponse]:
        """Assign verticals to user."""
        pass
    
    @abstractmethod
    def remove_vertical(self, db: Session, user_id: UUID, vertical_id: UUID,
                       requesting_user_id: UUID, requesting_user_role: str,
                       requesting_user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Remove vertical assignment from user."""
        pass
    
    @abstractmethod
    def validate_user_permissions(self, requesting_user_role: str, target_user_role: str,
                                 requesting_team_id: Optional[UUID], 
                                 target_team_id: Optional[UUID]) -> bool:
        """Validate if user has permission to perform action on target user."""
        pass
    
    @abstractmethod
    def validate_vertical_assignment_permission(self, db: Session, user_id: UUID,
                                               requesting_user_id: UUID, requesting_user_role: str,
                                               requesting_user_team_id: Optional[UUID] = None) -> bool:
        """Validate if user can assign verticals to target user."""
        pass
    
    @abstractmethod
    def get_team_members(self, db: Session, team_id: UUID,
                        requesting_user_id: UUID, requesting_user_role: str,
                        requesting_user_team_id: Optional[UUID] = None) -> List[UserResponse]:
        """Get team members with role-based access control."""
        pass
    
    @abstractmethod
    def check_username_availability(self, db: Session, username: str,
                                   exclude_user_id: Optional[UUID] = None) -> bool:
        """Check if username is available."""
        pass
    
    @abstractmethod
    def check_email_availability(self, db: Session, email: str,
                                exclude_user_id: Optional[UUID] = None) -> bool:
        """Check if email is available."""
        pass
    
    @abstractmethod
    def activate_user(self, db: Session, user_id: UUID) -> SuccessResponse:
        """Activate user account."""
        pass
    
    @abstractmethod
    def deactivate_user(self, db: Session, user_id: UUID) -> SuccessResponse:
        """Deactivate user account."""
        pass