from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from .base_repository import BaseRepository
from models.models import User, UserSession, UserVertical, UserRole, UserStatus, SessionStatus
from schemas.user import UserCreate, UserUpdate, UserListFilter
from schemas.auth import DeviceInfo
from schemas.common import PaginatedResponse
from interface.Irepositories.user_repository import IUserRepository
from utils.auth import get_password_hash
from utils.security import parse_user_agent
import logging
from sqlalchemy import asc, desc
from utils.sort_values import _apply_sorting

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User], IUserRepository):
    def __init__(self):
        super().__init__(User)

    def create(self, db: Session, user_data: UserCreate) -> User:
        """Create a new user."""
        hashed_password = get_password_hash(user_data.password)
        
        user_dict = user_data.dict(exclude={'password'})
        user_dict['hashed_password'] = hashed_password
        
        return super().create(db, **user_dict)

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email."""
        try:
            return db.query(User).filter(User.email == email).first()
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """Get user by username."""
        try:
            return db.query(User).filter(User.username == username).first()
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {e}")
            return None

    def get_all(self, db: Session, filters: UserListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get all users with filters and pagination."""
        try:
            query = db.query(User)
            
            # Apply filters
            if filters.role:
                query = query.filter(User.role == filters.role)
            
            if filters.status:
                query = query.filter(User.status == filters.status)
            
            if filters.team_id:
                query = query.filter(User.team_id == filters.team_id)
            
            if filters.q:
                search_term = f"%{filters.q}%"
                query = query.filter(
                    or_(
                        User.username.ilike(search_term),
                        User.first_name.ilike(search_term),
                        User.last_name.ilike(search_term),
                        User.email.ilike(search_term)
                    )
                )
            
            # Apply sorting
            query = _apply_sorting(query, sort_by, User)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            items = query.offset(skip).limit(limit).all()
            
            # Build next cursor if needed
            next_cursor = None
            if len(items) == limit and skip + limit < total_count:
                next_cursor = f"offset:{skip + limit}"
            
            return PaginatedResponse(
                items=items,
                next_cursor=next_cursor,
                count=len(items)
            )
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def update(self, db: Session, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        """Update user."""
        try:
            user = self.get_by_id(db, user_id)
            if not user:
                return None
            
            update_data = user_data.dict(exclude_unset=True)
            return super().update(db, user, **update_data)
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return None

    def delete(self, db: Session, user_id: UUID) -> bool:
        """Delete user."""
        try:
            # First delete related records
            db.query(UserVertical).filter(UserVertical.user_id == user_id).delete()
            db.query(UserSession).filter(UserSession.user_id == user_id).delete()
            
            # Then delete user
            return super().delete(db, user_id)
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    def update_last_login(self, db: Session, user_id: UUID) -> None:
        """Update user's last login timestamp."""
        try:
            user = self.get_by_id(db, user_id)
            if user:
                user.last_login = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
            db.rollback()

    def update_last_activity(self, db: Session, user_id: UUID) -> None:
        """Update user's last activity timestamp."""
        try:
            user = self.get_by_id(db, user_id)
            if user:
                user.last_activity = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Error updating last activity for user {user_id}: {e}")
            db.rollback()

    def get_team_members(self, db: Session, team_id: UUID) -> List[User]:
        """Get all members of a team."""
        try:
            return db.query(User).filter(
                and_(
                    User.team_id == team_id,
                    User.is_active == True
                )
            ).all()
        except Exception as e:
            logger.error(f"Error getting team members for team {team_id}: {e}")
            return []

    # Session management
    def create_session(self, db: Session, user_id: UUID, refresh_token: str, 
                      device_info: DeviceInfo, expires_at: datetime) -> UserSession:
        """Create user session."""
        try:
            device_data = parse_user_agent(device_info.user_agent)
            
            session = UserSession(
                user_id=user_id,
                refresh_token=refresh_token,
                status=SessionStatus.ACTIVE,
                ip_address=device_info.ip_address,
                user_agent=device_info.user_agent,
                os=device_data.get('os'),
                browser=device_data.get('browser'),
                browser_version=device_data.get('browser_version'),
                device_type=device_info.device_type,
                expires_at=expires_at
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        except Exception as e:
            logger.error(f"Error creating session for user {user_id}: {e}")
            db.rollback()
            raise

    def get_session_by_token(self, db: Session, refresh_token: str) -> Optional[UserSession]:
        """Get session by refresh token."""
        try:
            return db.query(UserSession).filter(
                and_(
                    UserSession.refresh_token == refresh_token,
                    UserSession.status == SessionStatus.ACTIVE,
                    UserSession.expires_at > datetime.utcnow()
                )
            ).first()
        except Exception as e:
            logger.error(f"Error getting session by token: {e}")
            return None

    def get_user_sessions(self, db: Session, user_id: UUID) -> List[UserSession]:
        """Get all sessions for a user."""
        try:
            return db.query(UserSession).filter(
                UserSession.user_id == user_id
            ).order_by(UserSession.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {e}")
            return []

    def invalidate_session(self, db: Session, session_id: UUID) -> bool:
        """Invalidate a session."""
        try:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if session:
                session.status = SessionStatus.INVALIDATED
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error invalidating session {session_id}: {e}")
            db.rollback()
            return False

    def invalidate_all_sessions(self, db: Session, user_id: UUID) -> None:
        """Invalidate all sessions for a user."""
        try:
            db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.status == SessionStatus.ACTIVE
                )
            ).update({"status": SessionStatus.INVALIDATED})
            db.commit()
        except Exception as e:
            logger.error(f"Error invalidating all sessions for user {user_id}: {e}")
            db.rollback()

    # Vertical assignments
    def get_user_verticals(self, db: Session, user_id: UUID) -> List[UserVertical]:
        """Get user's assigned verticals."""
        try:
            return db.query(UserVertical).filter(
                and_(
                    UserVertical.user_id == user_id,
                    UserVertical.is_active == True
                )
            ).all()
        except Exception as e:
            logger.error(f"Error getting verticals for user {user_id}: {e}")
            return []

    def assign_verticals(self, db: Session, user_id: UUID, vertical_ids: List[UUID], 
                        assigned_by_id: UUID, notes: Optional[str] = None) -> List[UserVertical]:
        """Assign verticals to user."""
        try:
            assignments = []
            for vertical_id in vertical_ids:
                # Check if assignment already exists
                existing = db.query(UserVertical).filter(
                    and_(
                        UserVertical.user_id == user_id,
                        UserVertical.vertical_id == vertical_id
                    )
                ).first()
                
                if existing:
                    existing.is_active = True
                    existing.assigned_by_id = assigned_by_id
                    existing.assigned_at = datetime.utcnow()
                    if notes:
                        existing.notes = notes
                    assignments.append(existing)
                else:
                    assignment = UserVertical(
                        user_id=user_id,
                        vertical_id=vertical_id,
                        assigned_by_id=assigned_by_id,
                        notes=notes
                    )
                    db.add(assignment)
                    assignments.append(assignment)
            
            db.commit()
            for assignment in assignments:
                db.refresh(assignment)
            
            return assignments
        except Exception as e:
            logger.error(f"Error assigning verticals to user {user_id}: {e}")
            db.rollback()
            return []

    def remove_vertical(self, db: Session, user_id: UUID, vertical_id: UUID) -> bool:
        """Remove vertical assignment from user."""
        try:
            assignment = db.query(UserVertical).filter(
                and_(
                    UserVertical.user_id == user_id,
                    UserVertical.vertical_id == vertical_id
                )
            ).first()
            
            if assignment:
                assignment.is_active = False
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing vertical {vertical_id} from user {user_id}: {e}")
            db.rollback()
            return False

    def check_vertical_assignment(self, db: Session, user_id: UUID, vertical_id: UUID) -> bool:
        """Check if user has access to a vertical."""
        try:
            assignment = db.query(UserVertical).filter(
                and_(
                    UserVertical.user_id == user_id,
                    UserVertical.vertical_id == vertical_id,
                    UserVertical.is_active == True
                )
            ).first()
            
            return assignment is not None
        except Exception as e:
            logger.error(f"Error checking vertical assignment for user {user_id}: {e}")
            return False