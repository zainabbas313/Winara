from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from models.models import UserRole, UserStatus


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    first_name: Optional[str] = Field(None,min_length=1, max_length=100)
    last_name: Optional[str] = Field(None,min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = None
    linkedin_profile_url: Optional[str] = None
    timezone: str = "UTC+05:00"


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    role: UserRole
    status: UserStatus = UserStatus.ACTIVE
    team_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = None
    linkedin_profile_url: Optional[str] = None
    timezone: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    team_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_locked: Optional[bool] = None

    @validator('username')
    def username_alphanumeric(cls, v):
        if v is not None:
            assert v.replace('_', '').replace('-', '').isalnum(), 'Username must be alphanumeric (with _ and - allowed)'
        return v


class UserResponse(UserBase):
    id: UUID
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


class UserListFilter(BaseModel):
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    team_id: Optional[UUID] = None
    q: Optional[str] = None


class UserSummary(BaseModel):
    id: UUID
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    role: UserRole
    status: UserStatus
    team_id: Optional[UUID] = None
    is_active: bool

    class Config:
        from_attributes = True
