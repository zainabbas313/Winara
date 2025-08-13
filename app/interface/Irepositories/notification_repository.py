from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from models.models import Notification, NotificationType
from schemas.notification import NotificationCreate, NotificationListFilter
from schemas.common import PaginatedResponse


class INotificationRepository(ABC):
    
    @abstractmethod
    def create(self, db: Session, notification_data: NotificationCreate) -> Notification:
        """Create a new notification."""
        pass
    
    @abstractmethod
    def get_by_id(self, db: Session, notification_id: UUID) -> Optional[Notification]:
        """Get notification by ID."""
        pass
    
    @abstractmethod
    def get_user_notifications(self, db: Session, user_id: UUID, filters: NotificationListFilter,
                              skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get user notifications with filters."""
        pass
    
    @abstractmethod
    def mark_as_read(self, db: Session, notification_id: UUID) -> Optional[Notification]:
        """Mark notification as read."""
        pass
    
    @abstractmethod
    def mark_all_as_read(self, db: Session, user_id: UUID) -> int:
        """Mark all user notifications as read and return count."""
        pass
    
    @abstractmethod
    def delete(self, db: Session, notification_id: UUID) -> bool:
        """Delete notification."""
        pass
    
    @abstractmethod
    def get_unread_count(self, db: Session, user_id: UUID) -> int:
        """Get count of unread notifications for user."""
        pass
    
    @abstractmethod
    def get_high_priority_unread(self, db: Session, user_id: UUID) -> List[Notification]:
        """Get high priority unread notifications."""
        pass
    
    @abstractmethod
    def create_bulk(self, db: Session, notifications: List[NotificationCreate]) -> List[Notification]:
        """Create multiple notifications."""
        pass
    
    @abstractmethod
    def get_unsent(self, db: Session, notification_type: NotificationType) -> List[Notification]:
        """Get unsent notifications of a specific type."""
        pass
    
    @abstractmethod
    def mark_as_sent(self, db: Session, notification_id: UUID) -> Optional[Notification]:
        """Mark notification as sent."""
        pass
    
    @abstractmethod
    def cleanup_old_notifications(self, db: Session, days_old: int = 90) -> int:
        """Clean up old read notifications and return count."""
        pass
    
    @abstractmethod
    def get_statistics(self, db: Session, user_id: UUID) -> Dict[str, Any]:
        """Get notification statistics for user."""
        pass
    
    @abstractmethod
    def create_system_notification(self, db: Session, user_ids: List[UUID], 
                                  title: str, message: str, priority: int = 1) -> List[Notification]:
        """Create system notification for multiple users."""
        pass
    
    @abstractmethod
    def create_bid_notification(self, db: Session, bid_id: UUID, notification_type: str) -> None:
        """Create bid-related notification."""
        pass
    
    @abstractmethod
    def create_payment_reminder(self, db: Session, receivable_id: UUID) -> None:
        """Create payment reminder notification."""
        pass