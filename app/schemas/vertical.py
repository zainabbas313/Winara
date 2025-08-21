from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal
import re

from models.models import UserRole
from schemas.user import UserSummary


class VerticalBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Vertical name")
    description: Optional[str] = Field(None, max_length=1000, description="Vertical description")
    parent_id: Optional[UUID] = Field(None, description="Parent vertical ID (None for root level)")
    level: Optional[int] = Field(None, ge=0, description="Hierarchy level (auto-calculated)")
    sort_order: int = Field(default=0, ge=0, description="Display order")
    is_active: bool = Field(default=True, description="Whether vertical is active")
    requires_approval: bool = Field(default=False, description="Whether assignments require approval")
    competition_level: int = Field(default=1, ge=1, le=10, description="Competition level (1-10)")


class VerticalCreate(VerticalBase):
    slug: str = Field(..., min_length=1, max_length=200, description="URL-friendly identifier")

    @validator('slug')
    def validate_slug(cls, v):
        if not v:
            raise ValueError('Slug is required')
        
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s\-_]', '', str(v).lower())
        slug = re.sub(r'[\s\-_]+', '-', slug).strip('-')
        
        if not slug:
            raise ValueError('Slug cannot be empty after formatting')
        
        return slug

    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Name is required and cannot be empty')
        return v.strip()


class VerticalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    parent_id: Optional[UUID] = None
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    requires_approval: Optional[bool] = None
    competition_level: Optional[int] = Field(None, ge=1, le=10)

    @validator('slug')
    def validate_slug(cls, v):
        if v is not None:
            slug = re.sub(r'[^a-zA-Z0-9\s\-_]', '', str(v).lower())
            slug = re.sub(r'[\s\-_]+', '-', slug).strip('-')
            if not slug:
                raise ValueError('Slug cannot be empty after formatting')
            return slug
        return v

    @validator('name')
    def validate_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Name cannot be empty')
        return v.strip() if v else v


class VerticalResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    level: int = Field(default=0)
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    requires_approval: bool = Field(default=False)
    total_earn: Optional[Decimal] = Field(default=Decimal('0.00'))
    connect_used: int = Field(default=0)
    total_bids: int = Field(default=0)
    avg_project_value: Optional[Decimal] = Field(default=None)
    competition_level: int = Field(default=1, ge=1, le=5)
    success_rate: Optional[Decimal] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    created_by_id: UUID

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None,
            datetime: lambda v: v.isoformat() if v is not None else None
        }


class VerticalListFilter(BaseModel):
    parent_id: Optional[UUID] = Field(None, description="Filter by parent vertical ID")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    q: Optional[str] = Field(None, description="Search in name, description, slug")


class VerticalSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    level: int
    is_active: bool
    total_bids: int = 0
    success_rate: Optional[Decimal] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None
        }


class VerticalStats(BaseModel):
    total_verticals: int
    active_verticals: int
    inactive_verticals: int
    total_earnings: float
    total_connects_used: int
    total_bids: int
    average_success_rate: float
    average_project_value: float
    average_competition_level: float
    level_distribution: Dict[int, int]


# User Vertical Assignment Schemas
class UserVerticalBase(BaseModel):
    is_active: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


class UserVerticalAssign(BaseModel):
    user_id: UUID
    vertical_ids: List[UUID] = Field(..., min_items=1, max_items=50)
    is_active: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


class UserVerticalResponse(UserVerticalBase):
    id: UUID
    user_id: UUID
    vertical_id: UUID
    assigned_at: datetime
    assigned_by_id: UUID
    total_earn: Optional[Decimal] = Field(default=0)
    connect_used: int = Field(default=0)
    total_bids: int = Field(default=0)
    success_rate: Optional[Decimal] = None
    vertical: VerticalSummary

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None
        }


class VerticalPerformanceTrend(BaseModel):
    date: str
    bids_count: int
    total_earned: float
    connects_used: int
    wins: int
    success_rate: float


class BulkVerticalOperation(BaseModel):
    vertical_ids: List[UUID] = Field(..., min_items=1, max_items=100)



# New schema for vertical user assignments
class VerticalUserAssignmentResponse(BaseModel):
    """Response schema for users assigned to a vertical"""
    assignment_id: UUID
    user: UserSummary
    assigned_at: datetime
    assigned_by_id: UUID
    is_active: bool
    total_earn: Optional[float] = Field(default=0)
    connect_used: int = Field(default=0)
    total_bids: int = Field(default=0)
    success_rate: Optional[float] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class VerticalAssignmentFilter(BaseModel):
    """Filter for vertical user assignments"""
    is_active: Optional[bool] = Field(None, description="Filter by assignment status")
    role: Optional[UserRole] = Field(None, description="Filter by user role")
    team_id: Optional[UUID] = Field(None, description="Filter by team ID")
    q: Optional[str] = Field(None, description="Search in user details")