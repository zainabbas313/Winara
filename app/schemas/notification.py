from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from ..models import NotificationType


class NotificationBase(BaseModel):
    type: NotificationType
    title: str = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1)
    priority: int = Field(default=1, ge=1, le=5)
    entity_type: Optional[str] = Field(None, max_length=100)
    entity_id: Optional[UUID] = None


class NotificationCreate(NotificationBase):
    user_id: UUID


class NotificationResponse(NotificationBase):
    id: UUID
    user_id: UUID
    is_read: bool = False
    is_sent: bool = False
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationMarkRead(BaseModel):
    is_read: bool = True


class NotificationReadResponse(BaseModel):
    id: UUID
    is_read: bool
    read_at: datetime


class NotificationListFilter(BaseModel):
    is_read: Optional[bool] = None
    type: Optional[NotificationType] = None
    since: Optional[datetime] = None


class NotificationStats(BaseModel):
    total_notifications: int
    unread_count: int
    high_priority_unread: int