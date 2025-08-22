from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from models.models import UserStatus


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE


class TeamCreate(TeamBase):
    sub_admin_id: UUID


class TeamUpdate(TeamBase):
    sub_admin_id: Optional[UUID] = None


class TeamResponse(TeamBase):
    id: UUID
    sub_admin_id: UUID
    total_earn: Optional[Decimal] = None
    total_connect_used: int = 0
    total_bids: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: UUID

    class Config:
        from_attributes = True


class TeamListFilter(BaseModel):
    status: Optional[UserStatus] = None
    sub_admin_id: Optional[UUID] = None
    q: Optional[str] = None


class TeamSummary(BaseModel):
    id: UUID
    name: str
    status: UserStatus
    total_bids: int
    total_earn: Optional[Decimal] = None

    class Config:
        from_attributes = True


# Team Goals
class TeamGoalBase(BaseModel):
    goal_name: str = Field(min_length=1, max_length=200)
    goal_type: str = Field(min_length=1, max_length=50)
    target_value: Decimal
    current_value: Decimal = Decimal('0')
    unit: str = Field(min_length=1, max_length=20)
    period_start: date
    period_end: date
    is_active: bool = True


class TeamGoalCreate(TeamGoalBase):
    pass


class TeamGoalUpdate(TeamGoalBase):
    is_achieved: Optional[bool] = None


class TeamGoalResponse(TeamGoalBase):
    id: UUID
    team_id: Optional[UUID] = None
    is_achieved: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: UUID

    class Config:
        from_attributes = True


class TeamMemberResponse(BaseModel):
    id: UUID
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    role: str
    status: str
    is_active: bool
    last_activity: Optional[datetime] = None

    class Config:
        from_attributes = True


class AddUserToTeamRequest(BaseModel):
    user_id: UUID = Field(..., description="ID of the user to add to the team")
    role: Optional[str] = Field(None, description="Role to assign (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "role": "member"
            }
        }


class RemoveUserFromTeamRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Reason for removal")
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "User transferred to another team"
            }
        }


class TeamMembershipResponse(BaseModel):
    user_id: UUID
    team_id: Optional[UUID] = None
    role: str
    added_by_id: UUID
    added_at: datetime
    status: str
    
    class Config:
        from_attributes = True


class BulkAddUsersRequest(BaseModel):
    user_ids: List[UUID] = Field(..., min_items=1, max_items=50)
    default_role: str = Field(default="member", description="Default role for all users")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001"
                ],
                "default_role": "member"
            }
        }


class BulkAddUsersResponse(BaseModel):
    success_count: int
    failed_count: int
    total_count: int
    added_users: List[TeamMemberResponse]
    failed_users: List[dict]
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "success_count": 2,
                "failed_count": 0,
                "total_count": 2,
                "added_users": [],
                "failed_users": [],
                "message": "Successfully added 2 users to team"
            }
        }