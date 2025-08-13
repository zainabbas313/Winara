from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Annotated
from database.database import get_db
from utils.auth import verify_token
from schemas.auth import TokenData
from models.models import User, UserRole
from repositories.user_repository import UserRepository
from services.auth_service import AuthService

security = HTTPBearer()

# Repository dependencies
def get_user_repository() -> UserRepository:
    return UserRepository()

def get_auth_service() -> AuthService:
    return AuthService()

# Authentication dependencies
async def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """Extract and validate JWT token from Authorization header."""
    token = credentials.credentials
    token_data = verify_token(token, "access")
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


async def get_current_user(
    db: Session = Depends(get_db),
    token_data: TokenData = Depends(get_current_user_token),
    user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """Get current user from token."""
    user = user_repo.get_by_id(db, token_data.user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )
    
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is locked",
        )
    
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require admin user."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_current_sub_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require sub-admin or admin user."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUB_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sub-admin or admin access required"
        )
    return current_user


# Optional authentication for public endpoints
async def get_current_user_optional(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository)
) -> Optional[User]:
    """Get current user if token is provided, otherwise return None."""
    if credentials is None:
        return None
    
    token = credentials.credentials
    token_data = verify_token(token, "access")
    
    if token_data is None:
        return None
    
    user = user_repo.get_by_id(db, token_data.user_id)
    
    if user is None or not user.is_active or user.is_locked:
        return None
    
    return user


# Request context utilities
def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP in case of multiple proxies
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request."""
    return request.headers.get("User-Agent", "unknown")


# Permission checking utilities
def check_team_access(user: User, target_team_id: Optional[str]) -> bool:
    """Check if user has access to team data."""
    if user.role == UserRole.ADMIN:
        return True
    
    if user.role == UserRole.SUB_ADMIN:
        return str(user.team_id) == target_team_id if target_team_id else True
    
    if user.role == UserRole.MEMBER:
        return str(user.team_id) == target_team_id if target_team_id else False
    
    return False


def check_user_access(requesting_user: User, target_user_id: str) -> bool:
    """Check if user has access to another user's data."""
    if requesting_user.role == UserRole.ADMIN:
        return True
    
    if str(requesting_user.id) == target_user_id:
        return True
    
    # Sub-admins can access their team members
    if requesting_user.role == UserRole.SUB_ADMIN:
        # This would need additional logic to check if target user is in same team
        return True
    
    return False


# Pagination utilities
def get_pagination_params(
    limit: int = 20,
    cursor: Optional[str] = None,
    sort: Optional[str] = None
) -> dict:
    """Get pagination parameters with validation."""
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    
    return {
        "limit": limit,
        "cursor": cursor,
        "sort": sort or "-created_at"
    }


# Common type aliases
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
CurrentSubAdminUser = Annotated[User, Depends(get_current_sub_admin_user)]
OptionalCurrentUser = Annotated[Optional[User], Depends(get_current_user_optional)]