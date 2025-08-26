# interface/Iservices/analytics_service.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime
from sqlalchemy.orm import Session
from schemas.analytics import (
    AnalyticsScope, DashboardAnalytics, ReportRequest, ReportResponse,
    BidPerformanceReport, FinancialReport, OperationalReport
)
from schemas.common import ExportRequest, ExportResponse
from models.models import UserRole


class IAnalyticsService(ABC):
    @abstractmethod
    def get_dashboard_analytics(
        self, db: Session, scope_data: AnalyticsScope,
        requesting_user_id: UUID, requesting_user_role: UserRole,
        requesting_user_team_id: Optional[UUID] = None
    ) -> DashboardAnalytics:
        pass

    @abstractmethod
    def generate_report(
        self, db: Session, report_request: ReportRequest,
        requesting_user_id: UUID, requesting_user_role: UserRole,
        requesting_user_team_id: Optional[UUID] = None
    ) -> ReportResponse:
        pass

    @abstractmethod
    def export_analytics(
        self, db: Session, export_request: ExportRequest,
        requesting_user_id: UUID, requesting_user_role: UserRole,
        requesting_user_team_id: Optional[UUID] = None
    ) -> ExportResponse:
        pass

    @abstractmethod
    def get_bid_performance_report(
        self, db: Session, team_id: Optional[UUID] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None,
        requesting_user_role: UserRole = None,
        requesting_user_team_id: Optional[UUID] = None
    ) -> BidPerformanceReport:
        pass

    @abstractmethod
    def get_financial_report(
        self, db: Session, team_id: Optional[UUID] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None,
        requesting_user_role: UserRole = None,
        requesting_user_team_id: Optional[UUID] = None
    ) -> FinancialReport:
        pass

    @abstractmethod
    def get_operational_report(
        self, db: Session, team_id: Optional[UUID] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None,
        requesting_user_role: UserRole = None,
        requesting_user_team_id: Optional[UUID] = None
    ) -> OperationalReport:
        pass

    @abstractmethod
    def get_performance_insights(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, requesting_user_role: UserRole = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_predictive_analytics(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, requesting_user_role: UserRole = None
    ) -> Dict[str, Any]:
        pass