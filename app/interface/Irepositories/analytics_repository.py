from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session


class IAnalyticsRepository(ABC):
    @abstractmethod
    def get_dashboard_kpis(
        self, db: Session, scope: str, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_bids_over_time(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None, granularity: str = 'day'
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_revenue_over_time(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None, granularity: str = 'day'
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_vertical_breakdown(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_team_performance(
        self, db: Session, date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_member_performance(
        self, db: Session, team_id: Optional[UUID] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_bid_performance_report(
        self, db: Session, team_id: Optional[UUID] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_financial_report(
        self, db: Session, team_id: Optional[UUID] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_operational_report(
        self, db: Session, team_id: Optional[UUID] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def cache_analytics_data(
        self, key: str, data: Dict[str, Any], ttl_minutes: int = 15
    ) -> None:
        pass

    @abstractmethod
    def get_cached_analytics_data(self, key: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_win_rate_trends(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, days: int = 30
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_cost_analysis(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_roi_analysis(
        self, db: Session, team_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        pass