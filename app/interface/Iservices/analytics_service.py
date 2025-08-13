from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from schemas.analytics import (
    AnalyticsScope, DashboardAnalytics, ReportRequest, ReportResponse,
    BidPerformanceReport, FinancialReport, OperationalReport
)
from schemas.common import ExportRequest, ExportResponse
from models.models import UserRole


class IAnalyticsService(ABC):
    
    @abstractmethod
    def get_dashboard_analytics(self, db: Session, scope_data: AnalyticsScope,
                               requesting_user_id: UUID, requesting_user_role: UserRole,
                               requesting_user_team_id: Optional[UUID] = None) -> DashboardAnalytics:
        """Get dashboard analytics with role-based access control."""
        pass
    
    @abstractmethod
    def generate_report(self, db: Session, report_request: ReportRequest,
                       requesting_user_id: UUID, requesting_user_role: UserRole,
                       requesting_user_team_id: Optional[UUID] = None) -> ReportResponse:
        """Generate analytics report with role-based filtering."""
        pass
    
    @abstractmethod
    def export_analytics(self, db: Session, export_request: ExportRequest,
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None) -> ExportResponse:
        """Export analytics data in various formats."""
        pass
    
    @abstractmethod
    def get_bid_performance_report(self, db: Session, team_id: Optional[UUID] = None,
                                  date_from: Optional[date] = None, date_to: Optional[date] = None,
                                  requesting_user_role: UserRole = None,
                                  requesting_user_team_id: Optional[UUID] = None) -> BidPerformanceReport:
        """Generate detailed bid performance report."""
        pass
    
    @abstractmethod
    def get_financial_report(self, db: Session, team_id: Optional[UUID] = None,
                            date_from: Optional[date] = None, date_to: Optional[date] = None,
                            requesting_user_role: UserRole = None,
                            requesting_user_team_id: Optional[UUID] = None) -> FinancialReport:
        """Generate financial report with revenue, costs, and profitability."""
        pass
    
    @abstractmethod
    def get_operational_report(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None, date_to: Optional[date] = None,
                              requesting_user_role: UserRole = None,
                              requesting_user_team_id: Optional[UUID] = None) -> OperationalReport:
        """Generate operational efficiency report."""
        pass
    
    @abstractmethod
    def validate_analytics_access(self, scope: str, requesting_user_role: UserRole,
                                 requested_team_id: Optional[UUID] = None,
                                 requested_user_id: Optional[UUID] = None,
                                 requesting_user_team_id: Optional[UUID] = None,
                                 requesting_user_id: Optional[UUID] = None) -> bool:
        """Validate if user has access to requested analytics scope."""
        pass
    
    @abstractmethod
    def get_performance_insights(self, db: Session, team_id: Optional[UUID] = None,
                                user_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get AI-powered performance insights and recommendations."""
        pass
    
    @abstractmethod
    def get_predictive_analytics(self, db: Session, team_id: Optional[UUID] = None,
                                user_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get predictive analytics for future performance."""
        pass
    
    @abstractmethod
    def get_competitive_analysis(self, db: Session, vertical_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get competitive analysis data."""
        pass
    
    @abstractmethod
    def cache_analytics_results(self, key: str, data: Dict[str, Any], ttl_minutes: int = 15) -> None:
        """Cache analytics results for performance."""
        pass
    
    @abstractmethod
    def get_cached_analytics(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached analytics data."""
        pass
    
    @abstractmethod
    def generate_analytics_cache_key(self, scope: str, params: Dict[str, Any]) -> str:
        """Generate cache key for analytics data."""
        pass