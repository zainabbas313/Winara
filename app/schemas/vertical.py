from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal
import re


class VerticalBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    level: int = Field(default=0, ge=0)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True
    requires_approval: bool = False
    competition_level: int = Field(default=1, ge=1, le=10)


class VerticalCreate(VerticalBase):
    slug: str = Field(min_length=1, max_length=200)

    @validator('slug')
    def slug_format(cls, v):
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s\-_]', '', v.lower())
        slug = re.sub(r'[\s\-_]+', '-', slug).strip('-')
        assert slug, 'Slug cannot be empty after formatting'
        return slug


class VerticalUpdate(VerticalBase):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=200)

    @validator('slug')
    def slug_format(cls, v):
        if v is not None:
            slug = re.sub(r'[^a-zA-Z0-9\s\-_]', '', v.lower())
            slug = re.sub(r'[\s\-_]+', '-', slug).strip('-')
            assert slug, 'Slug cannot be empty after formatting'
            return slug
        return v


class VerticalResponse(VerticalBase):
    id: UUID
    slug: str
    total_earn: Optional[Decimal] = None
    connect_used: int = 0
    total_bids: int = 0
    avg_project_value: Optional[Decimal] = None
    success_rate: Optional[Decimal] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: UUID

    class Config:
        from_attributes = True


class VerticalListFilter(BaseModel):
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    q: Optional[str] = None


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


# User Vertical Assignments
class UserVerticalBase(BaseModel):
    is_active: bool = True
    notes: Optional[str] = None


class UserVerticalAssign(BaseModel):
    vertical_ids: List[UUID] = Field(min_items=1)
    is_active: bool = True
    notes: Optional[str] = None


class UserVerticalResponse(UserVerticalBase):
    id: UUID
    user_id: UUID
    vertical_id: UUID
    assigned_at: datetime
    assigned_by_id: UUID
    total_earn: Optional[Decimal] = None
    connect_used: int = 0
    total_bids: int = 0
    success_rate: Optional[Decimal] = None
    vertical: VerticalSummary

    class Config:
        from_attributes = True


class VerticalStats(BaseModel):
    total_verticals: int
    active_verticals: int
    top_performing: List[VerticalSummary]
    lowest_performing: List[VerticalSummary]