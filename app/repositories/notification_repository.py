from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

from utils.helpers import calculate_overdue_days
from .base_repository import BaseRepository
from models.models import Notification, NotificationType, Team, User, Bid, Receivable
from schemas.notification import NotificationCreate, NotificationListFilter
from schemas.common import PaginatedResponse
from interface.Irepositories.notification_repository import INotificationRepository
import logging

logger = logging.getLogger(__name__)


class NotificationRepository(BaseRepository[Notification], INotificationRepository):
    def __init__(self):
        super().__init__(Notification)

    def create(self, db: Session, notification_data: NotificationCreate) -> Notification:
        """Create a new notification."""
        try:
            notification_dict = notification_data.dict()
            return super().create(db, **notification_dict)
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise

    def get_by_id(self, db: Session, notification_id: UUID) -> Optional[Notification]:
        """Get notification by ID."""
        try:
            return db.query(Notification).options(
                joinedload(Notification.user)
            ).filter(Notification.id == notification_id).first()
        except Exception as e:
            logger.error(f"Error getting notification {notification_id}: {e}")
            return None

    def get_user_notifications(self, db: Session, user_id: UUID, filters: NotificationListFilter,
                              skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get user notifications with filters."""
        try:
            query = db.query(Notification).filter(Notification.user_id == user_id)
            
            # Apply filters
            if filters.is_read is not None:
                query = query.filter(Notification.is_read == filters.is_read)
            
            if filters.type:
                query = query.filter(Notification.type == filters.type)
            
            if filters.since:
                query = query.filter(Notification.created_at >= filters.since)
            
            # Order by creation date (newest first)
            query = query.order_by(desc(Notification.created_at))
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            items = query.offset(skip).limit(limit).all()
            
            # Build next cursor if needed
            next_cursor = None
            if len(items) == limit and skip + limit < total_count:
                next_cursor = f"offset:{skip + limit}"
            
            return PaginatedResponse(
                items=items,
                next_cursor=next_cursor,
                count=len(items)
            )
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def mark_as_read(self, db: Session, notification_id: UUID) -> Optional[Notification]:
        """Mark notification as read."""
        try:
            notification = self.get_by_id(db, notification_id)
            if not notification:
                return None
            
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.commit()
            db.refresh(notification)
            
            return notification
        except Exception as e:
            logger.error(f"Error marking notification as read {notification_id}: {e}")
            db.rollback()
            return None

    def mark_all_as_read(self, db: Session, user_id: UUID) -> int:
        """Mark all user notifications as read and return count."""
        try:
            updated_count = db.query(Notification).filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                )
            ).update({
                "is_read": True,
                "read_at": datetime.utcnow()
            })
            
            db.commit()
            return updated_count
        except Exception as e:
            logger.error(f"Error marking all notifications as read for user {user_id}: {e}")
            db.rollback()
            return 0

    def delete(self, db: Session, notification_id: UUID) -> bool:
        """Delete notification."""
        return super().delete(db, notification_id)

    def get_unread_count(self, db: Session, user_id: UUID) -> int:
        """Get count of unread notifications for user."""
        try:
            return db.query(Notification).filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                )
            ).count()
        except Exception as e:
            logger.error(f"Error getting unread count for user {user_id}: {e}")
            return 0

    def get_high_priority_unread(self, db: Session, user_id: UUID) -> List[Notification]:
        """Get high priority unread notifications."""
        try:
            return db.query(Notification).filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                    Notification.priority >= 4  # High priority (4-5)
                )
            ).order_by(desc(Notification.priority), desc(Notification.created_at)).all()
        except Exception as e:
            logger.error(f"Error getting high priority notifications for user {user_id}: {e}")
            return []

    def create_bulk(self, db: Session, notifications: List[NotificationCreate]) -> List[Notification]:
        """Create multiple notifications."""
        try:
            notification_objects = []
            for notification_data in notifications:
                notification_dict = notification_data.dict()
                notification = Notification(**notification_dict)
                notification_objects.append(notification)
            
            db.add_all(notification_objects)
            db.commit()
            
            for notification in notification_objects:
                db.refresh(notification)
            
            return notification_objects
        except Exception as e:
            logger.error(f"Error creating bulk notifications: {e}")
            db.rollback()
            return []

    def get_unsent(self, db: Session, notification_type: NotificationType) -> List[Notification]:
        """Get unsent notifications of a specific type."""
        try:
            return db.query(Notification).filter(
                and_(
                    Notification.type == notification_type,
                    Notification.is_sent == False
                )
            ).order_by(Notification.created_at).all()
        except Exception as e:
            logger.error(f"Error getting unsent notifications: {e}")
            return []

    def mark_as_sent(self, db: Session, notification_id: UUID) -> Optional[Notification]:
        """Mark notification as sent."""
        try:
            notification = self.get_by_id(db, notification_id)
            if not notification:
                return None
            
            notification.is_sent = True
            notification.sent_at = datetime.utcnow()
            db.commit()
            db.refresh(notification)
            
            return notification
        except Exception as e:
            logger.error(f"Error marking notification as sent {notification_id}: {e}")
            db.rollback()
            return None

    def cleanup_old_notifications(self, db: Session, days_old: int = 90) -> int:
        """Clean up old read notifications and return count."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted_count = db.query(Notification).filter(
                and_(
                    Notification.is_read == True,
                    Notification.created_at < cutoff_date
                )
            ).delete()
            
            db.commit()
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {e}")
            db.rollback()
            return 0

    def get_statistics(self, db: Session, user_id: UUID) -> Dict[str, Any]:
        """Get notification statistics for user."""
        try:
            # Get overall counts
            total_notifications = db.query(Notification).filter(
                Notification.user_id == user_id
            ).count()
            
            unread_count = self.get_unread_count(db, user_id)
            
            # Get high priority unread count
            high_priority_unread = db.query(Notification).filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                    Notification.priority >= 4
                )
            ).count()
            
            # Get notifications by type
            type_breakdown = db.query(
                Notification.type,
                func.count(Notification.id).label('count'),
                func.count(func.case((Notification.is_read == False, 1))).label('unread_count')
            ).filter(
                Notification.user_id == user_id
            ).group_by(Notification.type).all()
            
            return {
                'total_notifications': total_notifications,
                'unread_count': unread_count,
                'high_priority_unread': high_priority_unread,
                'type_breakdown': [
                    {
                        'type': breakdown.type.value,
                        'total': breakdown.count,
                        'unread': breakdown.unread_count
                    }
                    for breakdown in type_breakdown
                ]
            }
        except Exception as e:
            logger.error(f"Error getting notification statistics for user {user_id}: {e}")
            return {}

    def create_system_notification(self, db: Session, user_ids: List[UUID], 
                                  title: str, message: str, priority: int = 1) -> List[Notification]:
        """Create system notification for multiple users."""
        try:
            notifications_data = [
                NotificationCreate(
                    user_id=user_id,
                    type=NotificationType.IN_APP,
                    title=title,
                    message=message,
                    priority=priority
                )
                for user_id in user_ids
            ]
            
            return self.create_bulk(db, notifications_data)
        except Exception as e:
            logger.error(f"Error creating system notifications: {e}")
            return []

    def create_bid_notification(self, db: Session, bid_id: UUID, notification_type: str) -> None:
        """Create bid-related notification."""
        try:
            # Get bid details
            bid = db.query(Bid).options(
                joinedload(Bid.member),
                joinedload(Bid.team)
            ).filter(Bid.id == bid_id).first()
            
            if not bid:
                logger.warning(f"Bid {bid_id} not found for notification")
                return
            
            # Create notification based on type
            if notification_type == "status_changed":
                title = f"Bid Status Updated: {bid.job_title}"
                message = f"Your bid for '{bid.job_title}' status has been updated to {bid.status.value}."
                priority = 2 if bid.status.value == "won" else 1
                
                notification_data = NotificationCreate(
                    user_id=bid.member_id,
                    type=NotificationType.IN_APP,
                    title=title,
                    message=message,
                    priority=priority,
                    entity_type="bid",
                    entity_id=bid_id
                )
                
                self.create(db, notification_data)
                
                # Also notify sub-admin if status is won
                if bid.status.value == "won" and bid.team and bid.team.sub_admin_id:
                    admin_notification = NotificationCreate(
                        user_id=bid.team.sub_admin_id,
                        type=NotificationType.IN_APP,
                        title=f"Team Bid Won: {bid.job_title}",
                        message=f"Team member {bid.member.first_name} {bid.member.last_name} won a bid for '{bid.job_title}'.",
                        priority=3,
                        entity_type="bid",
                        entity_id=bid_id
                    )
                    self.create(db, admin_notification)
                    
        except Exception as e:
            logger.error(f"Error creating bid notification: {e}")

    def create_payment_reminder(self, db: Session, receivable_id: UUID) -> None:
        """Create payment reminder notification."""
        try:
            # Get receivable details
            receivable = db.query(Receivable).options(
                joinedload(Receivable.team),
                joinedload(Receivable.team, Team.sub_admin)
            ).filter(Receivable.id == receivable_id).first()
            
            if not receivable or not receivable.team or not receivable.team.sub_admin:
                logger.warning(f"Receivable {receivable_id} not found or missing team/sub-admin")
                return
            
            days_overdue = calculate_overdue_days(receivable.expected_payment_date)
            
            if days_overdue > 0:
                title = f"Overdue Payment: {receivable.client_name}"
                message = f"Payment from {receivable.client_name} for '{receivable.project_title}' is {days_overdue} days overdue. Expected: {receivable.expected_payment_date}, Amount: {receivable.contract_value} {receivable.currency}."
                priority = 4  # High priority for overdue payments
            else:
                title = f"Payment Due Soon: {receivable.client_name}"
                message = f"Payment from {receivable.client_name} for '{receivable.project_title}' is due on {receivable.expected_payment_date}. Amount: {receivable.contract_value} {receivable.currency}."
                priority = 3  # Medium priority for upcoming payments
            
            notification_data = NotificationCreate(
                user_id=receivable.team.sub_admin_id,
                type=NotificationType.IN_APP,
                title=title,
                message=message,
                priority=priority,
                entity_type="receivable",
                entity_id=receivable_id
            )
            
            self.create(db, notification_data)
            
        except Exception as e:
            logger.error(f"Error creating payment reminder: {e}")