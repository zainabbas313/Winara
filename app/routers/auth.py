from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from dependencies.dependencies import (
    get_db, get_current_user, get_client_ip, get_user_agent,
    DatabaseSession, CurrentUser
)
from services.auth_service import AuthService
from schemas.auth import (
    DeviceInfo, LoginRequest, LoginResponse, RefreshTokenRequest, RefreshTokenResponse,
    LogoutRequest, ForgotPasswordRequest, ResetPasswordRequest,
    ChangePasswordRequest, UserSessionResponse
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_auth_service() -> AuthService:
    return AuthService()


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Authenticate user and create session.
    
    - **email**: User's email address
    - **password**: User's password
    - **device**: Device information for session tracking
    """
    try:
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        device_info = DeviceInfo(
                ip_address=ip_address,
                user_agent=user_agent,
                device_type="desktop"  # You can implement logic to detect this from user_agent
            )
        return auth_service.login(db, login_data, device_info)
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise


@router.post("/auth/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Refresh access token using refresh token.
    
    - **refresh_token**: Valid refresh token
    """
    return auth_service.refresh_token(db, refresh_data)


@router.post("/auth/logout", response_model=SuccessResponse)
async def logout(
    current_user: CurrentUser,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Logout user and invalidate session.
    
    - **session_id**: Session ID to invalidate
    """
    return auth_service.logout(db, current_user.id)


# @router.post("/auth/logout-all", response_model=SuccessResponse)
# async def logout_all_sessions(
#     current_user: CurrentUser,
#     db: DatabaseSession,
#     auth_service: AuthService = Depends(get_auth_service)
# ):
#     """
#     Logout user from all sessions.
#     """
#     return auth_service.logout_all_sessions(db, current_user.id)


@router.post("/auth/forgot-password", response_model=SuccessResponse)
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Send password reset email.
    
    - **email**: Email address to send reset link to
    """
    return auth_service.forgot_password(db, forgot_data)


@router.post("/auth/reset-password", response_model=SuccessResponse)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Reset password using reset token.
    
    - **token**: Password reset token from email
    - **new_password**: New password (must meet security requirements)
    """
    return auth_service.reset_password(db, reset_data)


@router.post("/auth/change-password", response_model=SuccessResponse)
async def change_password(
    change_data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Change user password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password (must meet security requirements)
    """
    return auth_service.change_password(db, change_data, current_user.id)


@router.get("/sessions", response_model=PaginatedResponse[UserSessionResponse])
async def get_user_sessions(
    current_user: CurrentUser,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Get all sessions for the current user.
    """
    return auth_service.get_user_sessions(db, current_user.id)


@router.delete("/sessions/{session_id}", response_model=SuccessResponse)
async def delete_session(
    session_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Delete a specific session.
    
    - **session_id**: ID of the session to delete
    """
    try:
        from uuid import UUID
        session_uuid = UUID(session_id)
        return auth_service.delete_session(db, session_uuid, current_user.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )


# Additional endpoints for session management and security

@router.get("/auth/me", response_model=dict)
async def get_current_user_info(current_user: CurrentUser):
    """
    Get current user information.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role,
        "status": current_user.status,
        "team_id": current_user.team_id,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_locked": current_user.is_locked,
        "last_login": current_user.last_login,
        "last_activity": current_user.last_activity,
        "created_at": current_user.created_at
    }


@router.post("/auth/validate-token", response_model=dict)
async def validate_token(
    current_user: CurrentUser
):
    """
    Validate the current access token.
    """
    return {
        "valid": True,
        "user_id": current_user.id,
        "role": current_user.role,
        "team_id": current_user.team_id
    }


@router.get("/auth/session-info", response_model=dict)
async def get_session_info(
    request: Request,
    current_user: CurrentUser
):
    """
    Get current session information.
    """
    return {
        "user_id": current_user.id,
        "ip_address": get_client_ip(request),
        "user_agent": get_user_agent(request),
        "authenticated": True,
        "role": current_user.role,
        "team_id": current_user.team_id
    }