from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from utils.security import validate_password_strength
from interface.Iservices.user_service import IUserService
from repositories.user_repository import UserRepository
from repositories.audit_repository import AuditRepository
from schemas.user import UserCreate, UserUpdate, UserResponse, UserListFilter
from schemas.vertical import UserVerticalAssign, UserVerticalResponse
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, UserStatus, AuditAction
from utils.auth import generate_password
from utils.validators import validate_username
import logging

logger = logging.getLogger(__name__)


class UserService(IUserService):
    def __init__(self):
        self.user_repo = UserRepository()
        self.audit_repo = AuditRepository()

    def create_user(self, db: Session, user_data: UserCreate, created_by_id: UUID) -> UserResponse:
        """Create a new user."""
        try:
            # Validate username
            is_valid, errors = validate_username(user_data.username)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Username validation failed: {', '.join(errors)}"
                )
            
            # Validate password strength
            is_valid, errors = validate_password_strength(user_data.password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Password validation failed: {', '.join(errors)}"
                )
            
            # Check if email already exists
            if self.user_repo.get_by_email(db, user_data.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Check if username already exists
            if self.user_repo.get_by_username(db, user_data.username):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            
            # Create user
            user = self.user_repo.create(db, user_data)
            
            # Log user creation
            self.audit_repo.create_audit_log(
                db, AuditAction.CREATE, "user", user.id, created_by_id, None,
                None, None, f"User created: {user.username} ({user.email})",
                old_values=None,
                new_values={
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value,
                    "team_id": str(user.team_id) if user.team_id else None
                }
            )
            
            return UserResponse.from_orm(user)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation failed"
            )

    def get_user(self, db: Session, user_id: UUID, requesting_user_id: UUID,
                requesting_user_role: str, requesting_user_team_id: Optional[UUID] = None) -> Optional[UserResponse]:
        """Get user by ID with role-based access control."""
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                return None
            
            # Check permissions
            if not self.validate_user_permissions(
                requesting_user_role, user.role.value,
                requesting_user_team_id, user.team_id
            ):
                # Check if user is requesting their own data
                if str(user_id) != str(requesting_user_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions to view this user"
                    )
            
            return UserResponse.from_orm(user)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    def get_users(self, db: Session, filters: UserListFilter, 
                 requesting_user_id: UUID, requesting_user_role: str, skip: int = 0,
                 limit: int = 20, sort_by: str = "-created_at",
                 requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[UserResponse]:
        """Get users with filters and role-based access control."""
        try:
            # Apply role-based filtering
            if requesting_user_role == UserRole.SUB_ADMIN.value:
                # Sub-admins can only see users in their team
                filters.team_id = requesting_user_team_id
            elif requesting_user_role == UserRole.MEMBER.value:
                # Members cannot access this endpoint
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            
            # Get users
            result = self.user_repo.get_all(db, filters, skip, limit, sort_by)
            
            # Convert to response objects
            user_responses = [UserResponse.from_orm(user) for user in result.items]
            
            return PaginatedResponse(
                items=user_responses,
                next_cursor=result.next_cursor,
                count=result.count
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def update_user(self, db: Session, user_id: UUID, user_data: UserUpdate,
                   requesting_user_id: UUID, requesting_user_role: str) -> Optional[UserResponse]:
        """Update user with role-based access control."""
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Store old values for audit
            old_values = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "role": user.role.value,
                "status": user.status.value,
                "team_id": str(user.team_id) if user.team_id else None
            }
            
            # Validate permissions and filter allowed fields
            filtered_data = self._filter_update_data(
                user_data, requesting_user_role, str(requesting_user_id), str(user_id)
            )
            
            # Validate username if being updated
            if filtered_data.username and filtered_data.username != user.username:
                is_valid, errors = validate_username(filtered_data.username)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Username validation failed: {', '.join(errors)}"
                    )
                
                if self.user_repo.get_by_username(db, filtered_data.username):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username already taken"
                    )
            
            # Update user
            updated_user = self.user_repo.update(db, user_id, filtered_data)
            if not updated_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User update failed"
                )
            
            # Create new values for audit
            new_values = {
                "username": updated_user.username,
                "first_name": updated_user.first_name,
                "last_name": updated_user.last_name,
                "email": updated_user.email,
                "role": updated_user.role.value,
                "status": updated_user.status.value,
                "team_id": str(updated_user.team_id) if updated_user.team_id else None
            }
            
            # Log user update
            self.audit_repo.create_audit_log(
                db, AuditAction.UPDATE, "user", user_id, requesting_user_id, None,
                None, None, f"User updated: {updated_user.username}",
                old_values=old_values,
                new_values=new_values
            )
            
            return UserResponse.from_orm(updated_user)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return None

    def delete_user(self, db: Session, user_id: UUID, requesting_user_id: UUID,
                   requesting_user_role: str) -> SuccessResponse:
        """Delete user with role-based access control."""
        try:
            # Only admins can delete users
            if requesting_user_role != UserRole.ADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only administrators can delete users"
                )
            
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Prevent self-deletion
            if str(user_id) == str(requesting_user_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete your own account"
                )
            
            # Store user info for audit
            user_info = {
                "username": user.username,
                "email": user.email,
                "role": user.role.value
            }
            
            # Delete user
            success = self.user_repo.delete(db, user_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User deletion failed"
                )
            
            # Log user deletion
            self.audit_repo.create_audit_log(
                db, AuditAction.DELETE, "user", user_id, requesting_user_id, None,
                None, None, f"User deleted: {user_info['username']}",
                old_values=user_info
            )
            
            return SuccessResponse(message="User deleted successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User deletion failed"
            )

    def get_user_verticals(self, db: Session, user_id: UUID,
                          requesting_user_id: UUID, requesting_user_role: str,
                          requesting_user_team_id: Optional[UUID] = None) -> List[UserVerticalResponse]:
        """Get user's assigned verticals."""
        try:
            # Validate access
            if not self.validate_vertical_assignment_permission(
                db, user_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view user verticals"
                )
            
            assignments = self.user_repo.get_user_verticals(db, user_id)
            return [UserVerticalResponse.from_orm(assignment) for assignment in assignments]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user verticals for {user_id}: {e}")
            return []

    def assign_verticals(self, db: Session, user_id: UUID, assignment_data: UserVerticalAssign,
                        assigned_by_id: UUID, requesting_user_role: str,
                        requesting_user_team_id: Optional[UUID] = None) -> List[UserVerticalResponse]:
        """Assign verticals to user."""
        try:
            # Validate permission
            if not self.validate_vertical_assignment_permission(
                db, user_id, assigned_by_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to assign verticals"
                )
            
            # Assign verticals
            assignments = self.user_repo.assign_verticals(
                db, user_id, assignment_data.vertical_ids, assigned_by_id, assignment_data.notes
            )
            
            # Log vertical assignments
            for assignment in assignments:
                self.audit_repo.create_audit_log(
                    db, AuditAction.ASSIGN_VERTICAL, "user_vertical", assignment.id,
                    assigned_by_id, None, None, None,
                    f"Vertical assigned to user: {assignment.vertical_id}",
                    new_values={
                        "user_id": str(user_id),
                        "vertical_id": str(assignment.vertical_id),
                        "notes": assignment_data.notes
                    }
                )
            
            return [UserVerticalResponse.from_orm(assignment) for assignment in assignments]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error assigning verticals to user {user_id}: {e}")
            return []

    def remove_vertical(self, db: Session, user_id: UUID, vertical_id: UUID,
                       requesting_user_id: UUID, requesting_user_role: str,
                       requesting_user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Remove vertical assignment from user."""
        try:
            # Validate permission
            if not self.validate_vertical_assignment_permission(
                db, user_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to remove vertical assignment"
                )
            
            # Remove vertical
            success = self.user_repo.remove_vertical(db, user_id, vertical_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vertical assignment not found"
                )
            
            # Log vertical removal
            self.audit_repo.create_audit_log(
                db, AuditAction.REMOVE_VERTICAL, "user_vertical", None,
                requesting_user_id, None, None, None,
                f"Vertical removed from user: {vertical_id}",
                old_values={
                    "user_id": str(user_id),
                    "vertical_id": str(vertical_id)
                }
            )
            
            return SuccessResponse(message="Vertical assignment removed successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error removing vertical {vertical_id} from user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Vertical removal failed"
            )

    def validate_user_permissions(self, requesting_user_role: str, target_user_role: str,
                                 requesting_team_id: Optional[UUID], 
                                 target_team_id: Optional[UUID]) -> bool:
        """Validate if user has permission to perform action on target user."""
        # Admins can access anyone
        if requesting_user_role == UserRole.ADMIN.value:
            return True
        
        # Sub-admins can access users in their team
        if requesting_user_role == UserRole.SUB_ADMIN.value:
            return requesting_team_id == target_team_id
        
        # Members have no access to other users' data
        return False

    def validate_vertical_assignment_permission(self, db: Session, user_id: UUID,
                                               requesting_user_id: UUID, requesting_user_role: str,
                                               requesting_user_team_id: Optional[UUID] = None) -> bool:
        """Validate if user can assign verticals to target user."""
        # Admins can assign to anyone
        if requesting_user_role == UserRole.ADMIN.value:
            return True
        
        # Sub-admins can assign to their team members
        if requesting_user_role == UserRole.SUB_ADMIN.value:
            target_user = self.user_repo.get_by_id(db, user_id)
            if target_user:
                return target_user.team_id == requesting_user_team_id
        
        # Members can only view their own verticals
        if requesting_user_role == UserRole.MEMBER.value:
            return str(user_id) == str(requesting_user_id)
        
        return False

    def get_team_members(self, db: Session, team_id: UUID,
                        requesting_user_id: UUID, requesting_user_role: str,
                        requesting_user_team_id: Optional[UUID] = None) -> List[UserResponse]:
        """Get team members with role-based access control."""
        try:
            # Validate access to team data
            if requesting_user_role == UserRole.MEMBER.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            
            if requesting_user_role == UserRole.SUB_ADMIN.value and team_id != requesting_user_team_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only access your own team members"
                )
            
            members = self.user_repo.get_team_members(db, team_id)
            return [UserResponse.from_orm(member) for member in members]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting team members for {team_id}: {e}")
            return []

    def check_username_availability(self, db: Session, username: str,
                                   exclude_user_id: Optional[UUID] = None) -> bool:
        """Check if username is available."""
        try:
            existing_user = self.user_repo.get_by_username(db, username)
            if existing_user:
                return exclude_user_id and existing_user.id == exclude_user_id
            return True
        except Exception as e:
            logger.error(f"Error checking username availability: {e}")
            return False

    def check_email_availability(self, db: Session, email: str,
                                exclude_user_id: Optional[UUID] = None) -> bool:
        """Check if email is available."""
        try:
            existing_user = self.user_repo.get_by_email(db, email)
            if existing_user:
                return exclude_user_id and existing_user.id == exclude_user_id
            return True
        except Exception as e:
            logger.error(f"Error checking email availability: {e}")
            return False

    def activate_user(self, db: Session, user_id: UUID) -> SuccessResponse:
        """Activate user account."""
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            update_data = UserUpdate(status=UserStatus.ACTIVE, is_active=True)
            self.user_repo.update(db, user_id, update_data)
            
            return SuccessResponse(message="User activated successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error activating user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User activation failed"
            )

    def deactivate_user(self, db: Session, user_id: UUID) -> SuccessResponse:
        """Deactivate user account."""
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            update_data = UserUpdate(status=UserStatus.INACTIVE, is_active=False)
            self.user_repo.update(db, user_id, update_data)
            
            # Invalidate all user sessions
            self.user_repo.invalidate_all_sessions(db, user_id)
            
            return SuccessResponse(message="User deactivated successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User deactivation failed"
            )

    def _filter_update_data(self, user_data: UserUpdate, requesting_user_role: str,
                           requesting_user_id: str, target_user_id: str) -> UserUpdate:
        """Filter update data based on role permissions."""
        # Admin can update everything
        if requesting_user_role == UserRole.ADMIN.value:
            return user_data
        
        # Create filtered data
        filtered_data = UserUpdate()
        
        # Sub-admins can update limited fields for their team members
        if requesting_user_role == UserRole.SUB_ADMIN.value:
            if user_data.first_name is not None:
                filtered_data.first_name = user_data.first_name
            if user_data.last_name is not None:
                filtered_data.last_name = user_data.last_name
            if user_data.phone is not None:
                filtered_data.phone = user_data.phone
            if user_data.bio is not None:
                filtered_data.bio = user_data.bio
            if user_data.linkedin_profile_url is not None:
                filtered_data.linkedin_profile_url = user_data.linkedin_profile_url
            return filtered_data
        
        # Members can only update their own basic info
        if requesting_user_role == UserRole.MEMBER.value and requesting_user_id == target_user_id:
            if user_data.first_name is not None:
                filtered_data.first_name = user_data.first_name
            if user_data.last_name is not None:
                filtered_data.last_name = user_data.last_name
            if user_data.phone is not None:
                filtered_data.phone = user_data.phone
            if user_data.bio is not None:
                filtered_data.bio = user_data.bio
            if user_data.linkedin_profile_url is not None:
                filtered_data.linkedin_profile_url = user_data.linkedin_profile_url
            if user_data.timezone is not None:
                filtered_data.timezone = user_data.timezone
            return filtered_data
        
        # No permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update user"
        )