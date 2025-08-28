from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from .base_repository import BaseRepository
from models.models import AuditLog, SecurityEvent, AuditAction, SecurityEventType, User, UserSession
from schemas.common import PaginatedResponse
from interface.Irepositories.audit_repository import IAuditRepository
import logging

logger = logging.getLogger(__name__)


class AuditRepository(BaseRepository[AuditLog], IAuditRepository):
    def __init__(self):
        super().__init__(AuditLog)

    def get_user_session_by_ids(self, db: Session, user_id: UUID, session_id: UUID) -> Optional[UserSession]:
        """Get complete user session by user ID and session ID with user relationship loaded."""
        try:
            session = db.query(UserSession).options(
                joinedload(UserSession.user)  # Eagerly load the related user
            ).filter(
                and_(
                    UserSession.id == session_id,
                    UserSession.user_id == user_id
                )
            ).first()
            
            return session
        except Exception as e:
            logger.error(f"Error getting user session for user {user_id}, session {session_id}: {e}")
            return None

    def create_audit_log(self, db: Session, action: AuditAction, entity_type: str,
                        entity_id: Optional[UUID], user_id: Optional[UUID],
                        session_id: Optional[UUID], ip_address: Optional[str],
                        user_agent: Optional[str], description: Optional[str],
                        old_values: Optional[Dict], new_values: Optional[Dict],
                        risk_level: int = 1) -> AuditLog:
        """Create audit log entry."""
        try:
            audit_log = AuditLog(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                description=description,
                old_values=old_values,
                new_values=new_values,
                risk_level=risk_level
            )
            
            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)
            
            return audit_log
        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
            db.rollback()
            raise

    def get_audit_logs(self, db: Session, user_id: Optional[UUID] = None,
                      action: Optional[AuditAction] = None, entity_type: Optional[str] = None,
                      date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                      ip_address: Optional[str] = None, skip: int = 0, 
                      limit: int = 20) -> PaginatedResponse:
        """Get audit logs with filters."""
        try:
            query = db.query(AuditLog).options(joinedload(AuditLog.user))
            
            # Apply filters
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            
            if action:
                query = query.filter(AuditLog.action == action)
            
            if entity_type:
                query = query.filter(AuditLog.entity_type == entity_type)
            
            if date_from:
                query = query.filter(AuditLog.timestamp >= date_from)
            
            if date_to:
                query = query.filter(AuditLog.timestamp <= date_to)
            
            if ip_address:
                query = query.filter(AuditLog.ip_address == ip_address)
            
            # Order by timestamp (newest first)
            query = query.order_by(desc(AuditLog.timestamp))
            
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
            logger.error(f"Error getting audit logs: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_user_activity(self, db: Session, user_id: UUID, days: int = 30) -> List[AuditLog]:
        """Get user activity for specified days."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            return db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.timestamp >= start_date
                )
            ).order_by(desc(AuditLog.timestamp)).all()
        except Exception as e:
            logger.error(f"Error getting user activity for {user_id}: {e}")
            return []

    def get_entity_history(self, db: Session, entity_type: str, entity_id: UUID) -> List[AuditLog]:
        """Get change history for an entity."""
        try:
            return db.query(AuditLog).options(joinedload(AuditLog.user)).filter(
                and_(
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id
                )
            ).order_by(AuditLog.timestamp).all()
        except Exception as e:
            logger.error(f"Error getting entity history for {entity_type}:{entity_id}: {e}")
            return []

    def create_security_event(self, db: Session, event_type: SecurityEventType,
                             severity: int, user_id: Optional[UUID],
                             session_id: Optional[UUID], ip_address: Optional[str],
                             user_agent: Optional[str], description: str,
                             additional_data: Optional[Dict] = None) -> SecurityEvent:
        """Create security event."""
        try:
            security_event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                description=description,
                additional_data=additional_data
            )
            
            db.add(security_event)
            db.commit()
            db.refresh(security_event)
            
            return security_event
        except Exception as e:
            logger.error(f"Error creating security event: {e}")
            db.rollback()
            raise

    def get_security_events(self, db: Session, event_type: Optional[SecurityEventType] = None,
                           severity: Optional[int] = None, user_id: Optional[UUID] = None,
                           resolved: Optional[bool] = None, skip: int = 0,
                           limit: int = 20) -> PaginatedResponse:
        """Get security events with filters."""
        try:
            query = db.query(SecurityEvent).options(joinedload(SecurityEvent.user))
            
            # Apply filters
            if event_type:
                query = query.filter(SecurityEvent.event_type == event_type)
            
            if severity is not None:
                query = query.filter(SecurityEvent.severity >= severity)
            
            if user_id:
                query = query.filter(SecurityEvent.user_id == user_id)
            
            if resolved is not None:
                query = query.filter(SecurityEvent.is_resolved == resolved)
            
            # Order by timestamp (newest first)
            query = query.order_by(desc(SecurityEvent.timestamp))
            
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
            logger.error(f"Error getting security events: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def resolve_security_event(self, db: Session, event_id: UUID) -> Optional[SecurityEvent]:
        """Mark security event as resolved."""
        try:
            event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
            if not event:
                return None
            
            event.is_resolved = True
            db.commit()
            db.refresh(event)
            
            return event
        except Exception as e:
            logger.error(f"Error resolving security event {event_id}: {e}")
            db.rollback()
            return None

    def get_high_risk_activities(self, db: Session, days: int = 7) -> List[AuditLog]:
        """Get high risk activities from recent days."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            return db.query(AuditLog).options(joinedload(AuditLog.user)).filter(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.risk_level >= 4  # High risk (4-5)
                )
            ).order_by(desc(AuditLog.risk_level), desc(AuditLog.timestamp)).all()
        except Exception as e:
            logger.error(f"Error getting high risk activities: {e}")
            return []

    def get_failed_login_attempts(self, db: Session, ip_address: Optional[str] = None,
                                 user_id: Optional[UUID] = None, 
                                 hours: int = 24) -> List[SecurityEvent]:
        """Get failed login attempts."""
        try:
            start_date = datetime.utcnow() - timedelta(hours=hours)
            
            query = db.query(SecurityEvent).filter(
                and_(
                    SecurityEvent.event_type == SecurityEventType.LOGIN_FAILED,
                    SecurityEvent.timestamp >= start_date
                )
            )
            
            if ip_address:
                query = query.filter(SecurityEvent.ip_address == ip_address)
            
            if user_id:
                query = query.filter(SecurityEvent.user_id == user_id)
            
            return query.order_by(desc(SecurityEvent.timestamp)).all()
        except Exception as e:
            logger.error(f"Error getting failed login attempts: {e}")
            return []

    def get_suspicious_activities(self, db: Session, days: int = 7) -> List[SecurityEvent]:
        """Get suspicious activities."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            return db.query(SecurityEvent).options(joinedload(SecurityEvent.user)).filter(
                and_(
                    SecurityEvent.event_type == SecurityEventType.SUSPICIOUS_ACTIVITY,
                    SecurityEvent.timestamp >= start_date,
                    SecurityEvent.is_resolved == False
                )
            ).order_by(desc(SecurityEvent.severity), desc(SecurityEvent.timestamp)).all()
        except Exception as e:
            logger.error(f"Error getting suspicious activities: {e}")
            return []

    def cleanup_old_logs(self, db: Session, days_old: int = 365) -> int:
        """Clean up old audit logs and return count."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Only delete low-risk logs that are older than the cutoff
            deleted_count = db.query(AuditLog).filter(
                and_(
                    AuditLog.timestamp < cutoff_date,
                    AuditLog.risk_level <= 2  # Only delete low-risk logs
                )
            ).delete()
            
            db.commit()
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old audit logs: {e}")
            db.rollback()
            return 0

    def get_login_statistics(self, db: Session, days: int = 30) -> Dict[str, Any]:
        """Get login statistics for specified period."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get login events
            login_events = db.query(SecurityEvent).filter(
                and_(
                    SecurityEvent.event_type.in_([
                        SecurityEventType.LOGIN_COMPLETED,
                        SecurityEventType.LOGIN_FAILED
                    ]),
                    SecurityEvent.timestamp >= start_date
                )
            ).all()
            
            # Calculate statistics
            total_attempts = len(login_events)
            successful_logins = len([e for e in login_events if e.event_type == SecurityEventType.LOGIN_COMPLETED])
            failed_logins = len([e for e in login_events if e.event_type == SecurityEventType.LOGIN_FAILED])
            
            # Get unique users and IPs
            unique_users = len(set(e.user_id for e in login_events if e.user_id))
            unique_ips = len(set(e.ip_address for e in login_events if e.ip_address))
            
            # Calculate daily statistics
            daily_stats = {}
            for event in login_events:
                day = event.timestamp.date()
                if day not in daily_stats:
                    daily_stats[day] = {'successful': 0, 'failed': 0}
                
                if event.event_type == SecurityEventType.LOGIN_COMPLETED:
                    daily_stats[day]['successful'] += 1
                else:
                    daily_stats[day]['failed'] += 1
            
            return {
                'period_days': days,
                'total_attempts': total_attempts,
                'successful_logins': successful_logins,
                'failed_logins': failed_logins,
                'success_rate': (successful_logins / total_attempts * 100) if total_attempts > 0 else 0,
                'unique_users': unique_users,
                'unique_ips': unique_ips,
                'daily_breakdown': [
                    {
                        'date': day.isoformat(),
                        'successful': stats['successful'],
                        'failed': stats['failed'],
                        'total': stats['successful'] + stats['failed']
                    }
                    for day, stats in sorted(daily_stats.items())
                ]
            }
        except Exception as e:
            logger.error(f"Error getting login statistics: {e}")
            return {}

    def log_data_access(self, db: Session, user_id: UUID, entity_type: str,
                       entity_id: UUID, action: str, ip_address: str) -> None:
        """Log sensitive data access."""
        try:
            risk_level = 1  # Default low risk
            
            # Increase risk level for certain entity types or actions
            if entity_type in ['user', 'financial_data', 'audit_log']:
                risk_level = 2
            
            if action in ['delete', 'export', 'bulk_operation']:
                risk_level = 3
            
            self.create_audit_log(
                db, AuditAction.CREATE, f"data_access_{entity_type}",
                entity_id, user_id, None, ip_address, None,
                f"Accessed {entity_type} data: {action}",
                old_values={},
                new_values={},
                risk_level=risk_level
            )
        except Exception as e:
            logger.error(f"Error logging data access: {e}")

    def detect_anomalies(self, db: Session, user_id: UUID) -> List[Dict[str, Any]]:
        """Detect anomalous user behavior."""
        try:
            anomalies = []
            
            # Get user's recent activity (last 30 days)
            recent_logs = self.get_user_activity(db, user_id, 30)
            
            if not recent_logs:
                return anomalies
            
            # Analyze login patterns
            login_logs = [log for log in recent_logs if log.action == AuditAction.LOGIN]
            if len(login_logs) > 1:
                # Check for unusual login times
                login_hours = [log.timestamp.hour for log in login_logs]
                avg_hour = sum(login_hours) / len(login_hours)
                
                for log in login_logs[-5:]:  # Check last 5 logins
                    if abs(log.timestamp.hour - avg_hour) > 6:  # More than 6 hours difference
                        anomalies.append({
                            'type': 'unusual_login_time',
                            'description': f'Login at unusual time: {log.timestamp.strftime("%H:%M")}',
                            'timestamp': log.timestamp,
                            'severity': 2
                        })
            
            # Check for unusual IP addresses
            ip_addresses = set(log.ip_address for log in login_logs if log.ip_address)
            if len(ip_addresses) > 3:  # More than 3 different IPs in 30 days
                anomalies.append({
                    'type': 'multiple_ip_addresses',
                    'description': f'Logins from {len(ip_addresses)} different IP addresses',
                    'timestamp': datetime.utcnow(),
                    'severity': 3
                })
            
            # Check for burst activity
            activity_by_day = {}
            for log in recent_logs:
                day = log.timestamp.date()
                activity_by_day[day] = activity_by_day.get(day, 0) + 1
            
            avg_daily_activity = sum(activity_by_day.values()) / len(activity_by_day)
            for day, count in activity_by_day.items():
                if count > avg_daily_activity * 3:  # 3x normal activity
                    anomalies.append({
                        'type': 'unusual_activity_burst',
                        'description': f'Unusually high activity on {day}: {count} actions',
                        'timestamp': datetime.combine(day, datetime.min.time()),
                        'severity': 2
                    })
            
            return anomalies
        except Exception as e:
            logger.error(f"Error detecting anomalies for user {user_id}: {e}")
            return []