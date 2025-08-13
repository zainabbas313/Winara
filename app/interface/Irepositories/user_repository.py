from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.models import User, UserSession, UserVertical
from schemas.user import UserCreate, UserUpdate, UserListFilter
from schemas.auth import DeviceInfo
from schemas.common import PaginatedResponse


class IUserRepository(ABC):
    
    @abstractmethod
    def create(self, db: Session, user_data: UserCreate) -> User:
        """Create a new user."""
        pass
    
    @abstractmethod
    def get_by_id(self, db: Session, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        pass
    
    @abstractmethod
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email."""
        pass
    
    @abstractmethod
    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """Get user by username."""
        pass
    
    @abstractmethod
    def get_all(self, db: Session, filters: UserListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get all users with filters and pagination."""
        pass
    
    @abstractmethod
    def update(self, db: Session, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        """Update user."""
        pass
    
    @abstractmethod
    def delete(self, db: Session, user_id: UUID) -> bool:
        """Delete user."""
        pass
    
    @abstractmethod
    def update_last_login(self, db: Session, user_id: UUID) -> None:
        """Update user's last login timestamp."""
        pass
    
    @abstractmethod
    def update_last_activity(self, db: Session, user_id: UUID) -> None:
        """Update user's last activity timestamp."""
        pass
    
    @abstractmethod
    def get_team_members(self, db: Session, team_id: UUID) -> List[User]:
        """Get all members of a team."""
        pass
    
    # Session management
    @abstractmethod
    def create_session(self, db: Session, user_id: UUID, refresh_token: str, 
                      device_info: DeviceInfo, expires_at) -> UserSession:
        """Create user session."""
        pass
    
    @abstractmethod
    def get_session_by_token(self, db: Session, refresh_token: str) -> Optional[UserSession]:
        """Get session by refresh token."""
        pass
    
    @abstractmethod
    def get_user_sessions(self, db: Session, user_id: UUID) -> List[UserSession]:
        """Get all sessions for a user."""
        pass
    
    @abstractmethod
    def invalidate_session(self, db: Session, session_id: UUID) -> bool:
        """Invalidate a session."""
        pass
    
    @abstractmethod
    def invalidate_all_sessions(self, db: Session, user_id: UUID) -> None:
        """Invalidate all sessions for a user."""
        pass
    
    # Vertical assignments
    @abstractmethod
    def get_user_verticals(self, db: Session, user_id: UUID) -> List[UserVertical]:
        """Get user's assigned verticals."""
        pass
    
    @abstractmethod
    def assign_verticals(self, db: Session, user_id: UUID, vertical_ids: List[UUID], 
                        assigned_by_id: UUID, notes: Optional[str] = None) -> List[UserVertical]:
        """Assign verticals to user."""
        pass
    
    @abstractmethod
    def remove_vertical(self, db: Session, user_id: UUID, vertical_id: UUID) -> bool:
        """Remove vertical assignment from user."""
        pass
    
    @abstractmethod
    def check_vertical_assignment(self, db: Session, user_id: UUID, vertical_id: UUID) -> bool:
        """Check if user has access to a vertical."""
        pass