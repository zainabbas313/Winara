"""
Audit logging utilities for tracking analytics access and operations.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from models.models import AuditLog, AuditAction

logger = logging.getLogger(__name__)


async def log_analytics_access(
    user_id: UUID,
    action: str,
    scope: Optional[str] = None,
    team_id: Optional[UUID] = None,
    target_user_id: Optional[UUID] = None,
    report_type: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    export_type: Optional[str] = None,
    format: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[UUID] = None
):
    """
    Log analytics access for audit purposes.
    
    This function creates audit log entries for analytics operations
    to maintain compliance and security tracking.
    """
    try:
        # In a real implementation, you would:
        # 1. Get database session
        # 2. Create audit log entry
        # 3. Store additional metadata
        
        audit_data = {
            "user_id": str(user_id),
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "scope": scope,
            "team_id": str(team_id) if team_id else None,
            "target_user_id": str(target_user_id) if target_user_id else None,
            "report_type": report_type,
            "filters": filters,
            "export_type": export_type,
            "format": format,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": str(session_id) if session_id else None
        }
        
        # Log to application logs
        logger.info(f"Analytics audit log: {action} by user {user_id}", extra=audit_data)
        
        # In production, you might also:
        # - Send to external audit service
        # - Store in dedicated audit database
        # - Send to SIEM system
        
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        # Don't raise exception as audit logging shouldn't break main functionality


def log_performance_metric(
    operation: str,
    duration_ms: float,
    user_id: Optional[UUID] = None,
    record_count: Optional[int] = None,
    cache_hit: bool = False
):
    """
    Log performance metrics for analytics operations.
    
    This helps monitor system performance and identify bottlenecks.
    """
    try:
        performance_data = {
            "operation": operation,
            "duration_ms": duration_ms,
            "user_id": str(user_id) if user_id else None,
            "record_count": record_count,
            "cache_hit": cache_hit,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Performance metric: {operation} took {duration_ms}ms", extra=performance_data)
        
        # Could also send to monitoring systems like Prometheus, DataDog, etc.
        
    except Exception as e:
        logger.error(f"Failed to log performance metric: {e}")

