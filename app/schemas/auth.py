from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from models.models import UserRole, UserStatus, SessionStatus


class DeviceInfo(BaseModel):
    ip_address: str
    user_agent: str
    os: Optional[str] = None
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    device_type: str = Field(pattern="^(desktop|mobile|tablet)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    expires_in: int
    refresh_token: str
    token_type: str = "bearer"


class SessionInfo(BaseModel):
    id: UUID
    status: SessionStatus
    expires_at: datetime


class UserProfile(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    linkedin_profile_url: Optional[str] = None
    timezone: str
    role: UserRole
    status: UserStatus
    team_id: Optional[UUID] = None
    is_active: bool
    is_verified: bool
    is_locked: bool
    last_login: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    expires_in: int
    refresh_token: str
    token_type: str = "bearer"
    session: SessionInfo
    user: UserProfile


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str = "bearer"
    session: SessionInfo


class LogoutRequest(BaseModel):
    session_id: UUID


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: SessionStatus
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    os: Optional[str] = None
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    device_type: Optional[str] = None
    created_at: datetime
    last_activity: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[UUID] = None
    role: Optional[UserRole] = None
    team_id: Optional[UUID] = None
    session_id: Optional[UUID] = None