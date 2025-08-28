from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from models.models import UserRole, UserStatus


from typing import Optional
from pydantic import BaseModel, Field, EmailStr, validator
import re

DISPOSABLE_DOMAINS = {"tempmail.com", "10minutemail.com", "mailinator.com"}

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = None
    linkedin_profile_url: Optional[str] = None
    timezone: str = "UTC+05:00"

    @validator("email")
    def validate_email(cls, email: str) -> str:
        email = email.lower()

        # Disallow consecutive dots
        if ".." in email:
            raise ValueError("Email cannot contain consecutive dots.")

        # Disallow starting/ending with dot
        if email.startswith(".") or email.endswith("."):
            raise ValueError("Email cannot start or end with a dot.")

        # Split into local part and domain
        try:
            local, domain = email.rsplit("@", 1)
        except ValueError:
            raise ValueError("Invalid email format.")

        # Disallow disposable domains
        if domain in DISPOSABLE_DOMAINS:
            raise ValueError("Disposable/temporary email addresses are not allowed.")

        # Disallow domain starting or ending with dot
        if domain.startswith(".") or domain.endswith("."):
            raise ValueError("Domain cannot start or end with a dot.")

        # Disallow `.com.com` or multiple consecutive TLDs
        if re.search(r"\.(com|net|org|edu|gov)\.(com|net|org|edu|gov)$", domain):
            raise ValueError("Invalid domain format (e.g., .com.com not allowed).")

        # Require valid domain structure (at least one dot, no empty labels)
        domain_parts = domain.split(".")
        if len(domain_parts) < 2 or any(not part for part in domain_parts):
            raise ValueError("Domain must contain a valid TLD (like example.com).")

        # Ensure TLD is alphabetic and >= 2 chars
        if not re.fullmatch(r"[a-z]{2,}", domain_parts[-1]):
            raise ValueError("Invalid top-level domain.")

        return email


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
