from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import and_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from interface.Iservices.auth_service import IAuthService
from repositories.user_repository import UserRepository
from repositories.audit_repository import AuditRepository
from schemas.auth import (
    DeviceInfo, LoginRequest, LoginResponse, RefreshTokenRequest, RefreshTokenResponse,
    LogoutRequest, ForgotPasswordRequest, ResetPasswordRequest, 
    ChangePasswordRequest, UserSessionResponse, TokenData, UserProfile,
    SessionInfo
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, UserSession, UserStatus, SessionStatus, AuditAction, SecurityEventType
from utils.auth import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, verify_token, create_password_reset_token,
    verify_password_reset_token
)
from utils.security import detect_suspicious_activity, calculate_risk_score,validate_password_strength
from core.config.config import settings
import logging

logger = logging.getLogger(__name__)


class AuthService(IAuthService):
    def __init__(self):
        self.user_repo = UserRepository()
        self.audit_repo = AuditRepository()

    def login(self, db: Session, login_data: LoginRequest, device_data: DeviceInfo) -> LoginResponse:
        """Authenticate user and create session."""
        try:
            # Get user by email
            print("1")
            user = self.user_repo.get_by_email(db, login_data.email)
            print("1")
            self.user_repo.invalidate_all_sessions(db, user.id)
            if not user:
                # Log failed login attempt
                print("1")
                self.audit_repo.create_security_event(
                    db, SecurityEventType.LOGIN_FAILED, 2, user.id, "",
                    device_data.ip_address, device_data.user_agent,
                    f"Login failed for email: {login_data.email}",
                    {"email": login_data.email}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            print("1")
            # Verify password
            if not verify_password(login_data.password, user.hashed_password):
                # Log failed login attempt
                self.audit_repo.create_security_event(
                    db, SecurityEventType.LOGIN_FAILED, 2, user.id, None,
                    device_data.ip_address, device_data.user_agent,
                    "Invalid password provided"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            print("1")
            # Check user status
            if not user.is_active or user.status != UserStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is inactive"
                )
            
            if user.is_locked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is locked"
                )
            
            # Check for suspicious activity
            suspicious = self.detect_suspicious_activity(db, user.id, device_data.ip_address)
            if suspicious:
                self.audit_repo.create_security_event(
                    db, SecurityEventType.SUSPICIOUS_ACTIVITY, 4, user.id, None,
                    device_data.ip_address, device_data.user_agent,
                    "Suspicious login pattern detected"
                )
                # Could implement additional security measures here
            
            # Create session first (without refresh token in DB)
            expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            session = self.user_repo.create_session(
                db, user.id, device_data, expires_at
            )
            
            # Create tokens with session_id included
            token_data = {
                "sub": str(user.id),
                "role": user.role.value,
                "team_id": str(user.team_id) if user.team_id else None,
                "session_id": str(session.id)
            }
            
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token(token_data)
            
            # Update user's last login
            self.user_repo.update_last_login(db, user.id)
            
            # Log successful login
            self.audit_repo.create_audit_log(
                db, AuditAction.LOGIN, "user", user.id, user.id, session.id,
                device_data.ip_address, device_data.user_agent,
                "User logged in successfully", None, None
            )
            
            # Create response
            user_profile = UserProfile.from_orm(user)
            session_info = SessionInfo(
                id=session.id,
                status=session.status,
                expires_at=session.expires_at
            )
            
            return LoginResponse(
                access_token=access_token,
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                refresh_token=refresh_token,
                session=session_info,
                user=user_profile
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during login: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed"
            )
    def refresh_token(self, db: Session, refresh_data: RefreshTokenRequest) -> RefreshTokenResponse:
        """Refresh access token using refresh token."""
        try:
            # Verify refresh token
            token_data = verify_token(refresh_data.refresh_token, "refresh")
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Get session by refresh token
            session = self.user_repo.get_session_by_user_id(db, token_data.user_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session not found or expired"
                )
            
            # Get user
            user = self.user_repo.get_by_id(db, token_data.user_id)
            if not user or not user.is_active or user.is_locked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is inactive"
                )
            
            # Create new access token
            new_token_data = {
                "sub": str(user.id),
                "role": user.role.value,
                "team_id": str(user.team_id) if user.team_id else None,
                "session_id": str(session.id)
            }
            
            access_token = create_access_token(new_token_data)
            
            # Update session activity
            session.last_activity = datetime.utcnow()
            db.commit()
            
            session_info = SessionInfo(
                id=session.id,
                status=session.status,
                expires_at=session.expires_at
            )
            
            return RefreshTokenResponse(
                access_token=access_token,
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                session=session_info
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed"
            )

    def logout(self, db: Session, current_user_id: UUID) -> SuccessResponse:
        """Logout user and invalidate session."""
        try:
            # Invalidate session
            self.user_repo.invalidate_all_sessions(db, current_user_id)
            # success = self.user_repo.invalidate_session(db, logout_data.session_id)
            
            # if success:
            #     # Log logout
            #     self.audit_repo.create_audit_log(
            #         db, AuditAction.LOGOUT, "user", current_user_id, current_user_id,
            #         logout_data.session_id, None, None, "User logged out", old_values={}, new_values={}
            #     )
            
            return SuccessResponse(message="Logged out successfully")
            
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed"
            )

    def logout_all_sessions(self, db: Session, user_id: UUID) -> SuccessResponse:
        """Logout user from all sessions."""
        try:
            self.user_repo.invalidate_all_sessions(db, user_id)
            
            # Log logout from all sessions
            self.audit_repo.create_audit_log(
                db, AuditAction.LOGOUT, "user", user_id, user_id, None,
                None, None, "User logged out from all sessions", old_values={}, new_values={}
            )
            
            return SuccessResponse(message="Logged out from all sessions")
            
        except Exception as e:
            logger.error(f"Error logging out all sessions: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed"
            )

    def forgot_password(self, db: Session, forgot_data: ForgotPasswordRequest) -> SuccessResponse:
        """Send password reset email."""
        try:
            user = self.user_repo.get_by_email(db, forgot_data.email)
            
            if user and user.is_active:
                # Create password reset token
                reset_token = create_password_reset_token(user.email)
                
                # Here you would send the reset email
                # For now, just log it
                logger.info(f"Password reset token for {user.email}: {reset_token}")
                
                # Log password reset request
                self.audit_repo.create_security_event(
                    db, SecurityEventType.PASSWORD_RESET_INITIATED, 1, user.id, None,
                    None, None, "Password reset requested", None
                )
            
            # Always return success to prevent email enumeration
            return SuccessResponse(message="If the email exists, a reset link has been sent")
            
        except Exception as e:
            logger.error(f"Error in forgot password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password reset request failed"
            )

    def reset_password(self, db: Session, reset_data: ResetPasswordRequest) -> SuccessResponse:
        """Reset password using reset token."""
        try:
            # Verify reset token
            email = verify_password_reset_token(reset_data.token)
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset token"
                )
            
            # Get user
            user = self.user_repo.get_by_email(db, email)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Validate password strength
            is_valid, errors = validate_password_strength(reset_data.new_password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Password validation failed: {', '.join(errors)}"
                )
            
            # Update password
            user.hashed_password = get_password_hash(reset_data.new_password)
            db.commit()
            
            # Invalidate all sessions
            self.user_repo.invalidate_all_sessions(db, user.id)
            
            # Log password reset
            self.audit_repo.create_security_event(
                db, SecurityEventType.PASSWORD_RESET_COMPLETED, 1, user.id, None,
                None, None, "Password reset completed", None
            )
            
            return SuccessResponse(message="Password reset successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password reset failed"
            )

    def change_password(self, db: Session, change_data: ChangePasswordRequest, 
                       current_user_id: UUID) -> SuccessResponse:
        """Change user password."""
        try:
            # Get user
            user = self.user_repo.get_by_id(db, current_user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Verify current password
            if not verify_password(change_data.current_password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
            
            # Validate new password strength
            is_valid, errors = validate_password_strength(change_data.new_password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Password validation failed: {', '.join(errors)}"
                )
            
            # Update password
            user.hashed_password = get_password_hash(change_data.new_password)
            db.commit()
            
            # Log password change
            self.audit_repo.create_security_event(
                db, SecurityEventType.PASSWORD_CHANGED, 1, user.id, None,
                None, None, "Password changed by user", None
            )
            
            return SuccessResponse(message="Password changed successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )

    def get_current_user(self, db: Session, token: str) -> Optional[TokenData]:
        """Get current user from token."""
        return verify_token(token, "access")

    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode JWT token."""
        return verify_token(token, "access")

    def get_user_sessions(self, db: Session, user_id: UUID) -> PaginatedResponse[UserSessionResponse]:
        """Get all sessions for a user."""
        try:
            sessions = self.user_repo.get_user_sessions(db, user_id)
            session_responses = [UserSessionResponse.from_orm(session) for session in sessions]
            
            return PaginatedResponse(
                items=session_responses,
                next_cursor=None,
                count=len(session_responses)
            )
            
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def delete_session(self, db: Session, session_id: UUID, current_user_id: UUID) -> SuccessResponse:
        """Delete a specific session."""
        try:
            success = self.user_repo.invalidate_session(db, session_id)
            
            if success:
                self.audit_repo.create_audit_log(
                    db, AuditAction.DELETE, "session", session_id, current_user_id,
                    session_id, None, None, "Session deleted by user", old_values={},new_values={}
                )
            
            return SuccessResponse(message="Session deleted successfully")
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Session deletion failed"
            )

    def validate_session(self, db: Session, session_id: UUID) -> bool:
        """Validate if session is still active."""
        try:
            session = db.query(UserSession).filter(
                and_(
                    UserSession.id == session_id,
                    UserSession.status == SessionStatus.ACTIVE,
                    UserSession.expires_at > datetime.utcnow()
                )
            ).first()
            
            return session is not None
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False

    def detect_suspicious_activity(self, db: Session, user_id: UUID, 
                                  ip_address: str) -> bool:
        """Detect suspicious login activity."""
        try:
            # Get recent login attempts
            recent_attempts = self.audit_repo.get_failed_login_attempts(
                db, ip_address=ip_address, user_id=user_id, hours=24
            )
            
            return detect_suspicious_activity([
                {
                    'timestamp': attempt.timestamp,
                    'ip_address': attempt.ip_address
                }
                for attempt in recent_attempts
            ])
            
        except Exception as e:
            logger.error(f"Error detecting suspicious activity: {e}")
            return False

    def lock_user_account(self, db: Session, user_id: UUID, reason: str) -> None:
        """Lock user account due to security concerns."""
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if user:
                user.is_locked = True
                db.commit()
                
                # Invalidate all sessions
                self.user_repo.invalidate_all_sessions(db, user_id)
                
                # Log account lock
                self.audit_repo.create_security_event(
                    db, SecurityEventType.ACCOUNT_LOCKED, 3, user_id, None,
                    None, None, f"Account locked: {reason}", None
                )
                
        except Exception as e:
            logger.error(f"Error locking user account: {e}")
            db.rollback()

    def unlock_user_account(self, db: Session, user_id: UUID) -> None:
        """Unlock user account."""
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if user:
                user.is_locked = False
                db.commit()
                
                # Log account unlock
                self.audit_repo.create_security_event(
                    db, SecurityEventType.ACCOUNT_UNLOCKED, 1, user_id, None,
                    None, None, "Account unlocked by administrator", None
                )
                
        except Exception as e:
            logger.error(f"Error unlocking user account: {e}")
            db.rollback()