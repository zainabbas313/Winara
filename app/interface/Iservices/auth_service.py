from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.auth import (
    LoginRequest, LoginResponse, RefreshTokenRequest, RefreshTokenResponse,
    LogoutRequest, ForgotPasswordRequest, ResetPasswordRequest, 
    ChangePasswordRequest, UserSessionResponse, TokenData
)
from schemas.common import SuccessResponse, PaginatedResponse


class IAuthService(ABC):
    
    @abstractmethod
    def login(self, db: Session, login_data: LoginRequest) -> LoginResponse:
        """Authenticate user and create session."""
        pass
    
    @abstractmethod
    def refresh_token(self, db: Session, refresh_data: RefreshTokenRequest) -> RefreshTokenResponse:
        """Refresh access token using refresh token."""
        pass
    
    @abstractmethod
    def logout(self, db: Session, logout_data: LogoutRequest, current_user_id: UUID) -> SuccessResponse:
        """Logout user and invalidate session."""
        pass
    
    @abstractmethod
    def logout_all_sessions(self, db: Session, user_id: UUID) -> SuccessResponse:
        """Logout user from all sessions."""
        pass
    
    @abstractmethod
    def forgot_password(self, db: Session, forgot_data: ForgotPasswordRequest) -> SuccessResponse:
        """Send password reset email."""
        pass
    
    @abstractmethod
    def reset_password(self, db: Session, reset_data: ResetPasswordRequest) -> SuccessResponse:
        """Reset password using reset token."""
        pass
    
    @abstractmethod
    def change_password(self, db: Session, change_data: ChangePasswordRequest, 
                       current_user_id: UUID) -> SuccessResponse:
        """Change user password."""
        pass
    
    @abstractmethod
    def get_current_user(self, db: Session, token: str) -> Optional[TokenData]:
        """Get current user from token."""
        pass
    
    @abstractmethod
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode JWT token."""
        pass
    
    @abstractmethod
    def get_user_sessions(self, db: Session, user_id: UUID) -> PaginatedResponse[UserSessionResponse]:
        """Get all sessions for a user."""
        pass
    
    @abstractmethod
    def delete_session(self, db: Session, session_id: UUID, current_user_id: UUID) -> SuccessResponse:
        """Delete a specific session."""
        pass
    
    @abstractmethod
    def validate_session(self, db: Session, session_id: UUID) -> bool:
        """Validate if session is still active."""
        pass
    
    @abstractmethod
    def detect_suspicious_activity(self, db: Session, user_id: UUID, 
                                  ip_address: str) -> bool:
        """Detect suspicious login activity."""
        pass
    
    @abstractmethod
    def lock_user_account(self, db: Session, user_id: UUID, reason: str) -> None:
        """Lock user account due to security concerns."""
        pass
    
    @abstractmethod
    def unlock_user_account(self, db: Session, user_id: UUID) -> None:
        """Unlock user account."""
        pass