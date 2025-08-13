from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from models.models import AuditLog, SecurityEvent, AuditAction, SecurityEventType
from schemas.common import PaginatedResponse


class IAuditRepository(ABC):
    
    @abstractmethod
    def create_audit_log(self, db: Session, action: AuditAction, entity_type: str,
                        entity_id: Optional[UUID], user_id: Optional[UUID],
                        session_id: Optional[UUID], ip_address: Optional[str],
                        user_agent: Optional[str], description: Optional[str],
                        old_values: Optional[Dict], new_values: Optional[Dict],
                        risk_level: int = 1) -> AuditLog:
        """Create audit log entry."""
        pass
    
    @abstractmethod
    def get_audit_logs(self, db: Session, user_id: Optional[UUID] = None,
                      action: Optional[AuditAction] = None, entity_type: Optional[str] = None,
                      date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                      ip_address: Optional[str] = None, skip: int = 0, 
                      limit: int = 20) -> PaginatedResponse:
        """Get audit logs with filters."""
        pass
    
    @abstractmethod
    def get_user_activity(self, db: Session, user_id: UUID, days: int = 30) -> List[AuditLog]:
        """Get user activity for specified days."""
        pass
    
    @abstractmethod
    def get_entity_history(self, db: Session, entity_type: str, entity_id: UUID) -> List[AuditLog]:
        """Get change history for an entity."""
        pass
    
    @abstractmethod
    def create_security_event(self, db: Session, event_type: SecurityEventType,
                             severity: int, user_id: Optional[UUID],
                             session_id: Optional[UUID], ip_address: Optional[str],
                             user_agent: Optional[str], description: str,
                             additional_data: Optional[Dict] = None) -> SecurityEvent:
        """Create security event."""
        pass
    
    @abstractmethod
    def get_security_events(self, db: Session, event_type: Optional[SecurityEventType] = None,
                           severity: Optional[int] = None, user_id: Optional[UUID] = None,
                           resolved: Optional[bool] = None, skip: int = 0,
                           limit: int = 20) -> PaginatedResponse:
        """Get security events with filters."""
        pass
    
    @abstractmethod
    def resolve_security_event(self, db: Session, event_id: UUID) -> Optional[SecurityEvent]:
        """Mark security event as resolved."""
        pass
    
    @abstractmethod
    def get_high_risk_activities(self, db: Session, days: int = 7) -> List[AuditLog]:
        """Get high risk activities from recent days."""
        pass
    
    @abstractmethod
    def get_failed_login_attempts(self, db: Session, ip_address: Optional[str] = None,
                                 user_id: Optional[UUID] = None, 
                                 hours: int = 24) -> List[SecurityEvent]:
        """Get failed login attempts."""
        pass
    
    @abstractmethod
    def get_suspicious_activities(self, db: Session, days: int = 7) -> List[SecurityEvent]:
        """Get suspicious activities."""
        pass
    
    @abstractmethod
    def cleanup_old_logs(self, db: Session, days_old: int = 365) -> int:
        """Clean up old audit logs and return count."""
        pass
    
    @abstractmethod
    def get_login_statistics(self, db: Session, days: int = 30) -> Dict[str, Any]:
        """Get login statistics for specified period."""
        pass
    
    @abstractmethod
    def log_data_access(self, db: Session, user_id: UUID, entity_type: str,
                       entity_id: UUID, action: str, ip_address: str) -> None:
        """Log sensitive data access."""
        pass
    
    @abstractmethod
    def detect_anomalies(self, db: Session, user_id: UUID) -> List[Dict[str, Any]]:
        """Detect anomalous user behavior."""
        pass