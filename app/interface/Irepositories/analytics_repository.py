from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.orm import Session


class IAnalyticsRepository(ABC):
    
    @abstractmethod
    def get_dashboard_kpis(self, db: Session, scope: str, team_id: Optional[UUID] = None,
                          user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                          date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get dashboard KPIs for specified scope and filters."""
        pass
    
    @abstractmethod
    def get_bids_over_time(self, db: Session, team_id: Optional[UUID] = None,
                          user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                          date_to: Optional[date] = None, granularity: str = 'day') -> List[Dict[str, Any]]:
        """Get bids over time chart data."""
        pass
    
    @abstractmethod
    def get_revenue_over_time(self, db: Session, team_id: Optional[UUID] = None,
                             user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                             date_to: Optional[date] = None, granularity: str = 'day') -> List[Dict[str, Any]]:
        """Get revenue over time chart data."""
        pass
    
    @abstractmethod
    def get_vertical_breakdown(self, db: Session, team_id: Optional[UUID] = None,
                              user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get vertical performance breakdown."""
        pass
    
    @abstractmethod
    def get_team_performance(self, db: Session, date_from: Optional[date] = None,
                            date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get team performance comparison."""
        pass
    
    @abstractmethod
    def get_member_performance(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get member performance data."""
        pass
    
    @abstractmethod
    def get_bid_performance_report(self, db: Session, team_id: Optional[UUID] = None,
                                  date_from: Optional[date] = None,
                                  date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate bid performance report."""
        pass
    
    @abstractmethod
    def get_financial_report(self, db: Session, team_id: Optional[UUID] = None,
                            date_from: Optional[date] = None,
                            date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate financial report."""
        pass
    
    @abstractmethod
    def get_operational_report(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate operational report."""
        pass
    
    @abstractmethod
    def get_win_rate_trends(self, db: Session, team_id: Optional[UUID] = None,
                           user_id: Optional[UUID] = None, days: int = 30) -> List[Dict[str, Any]]:
        """Get win rate trends over time."""
        pass
    
    @abstractmethod
    def get_cost_analysis(self, db: Session, team_id: Optional[UUID] = None,
                         user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                         date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get cost analysis data."""
        pass
    
    @abstractmethod
    def get_roi_analysis(self, db: Session, team_id: Optional[UUID] = None,
                        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                        date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get ROI analysis data."""
        pass
    
    @abstractmethod
    def get_client_analysis(self, db: Session, team_id: Optional[UUID] = None,
                           date_from: Optional[date] = None,
                           date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get client analysis data."""
        pass
    
    @abstractmethod
    def get_success_patterns(self, db: Session, team_id: Optional[UUID] = None,
                            user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Analyze success patterns."""
        pass
    
    @abstractmethod
    def get_predictive_insights(self, db: Session, team_id: Optional[UUID] = None,
                               user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get predictive insights based on historical data."""
        pass
    
    @abstractmethod
    def get_competitive_analysis(self, db: Session, vertical_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get competitive analysis by vertical."""
        pass
    
    @abstractmethod
    def cache_analytics_data(self, key: str, data: Dict[str, Any], ttl_minutes: int = 15) -> None:
        """Cache analytics data."""
        pass
    
    @abstractmethod
    def get_cached_analytics_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached analytics data."""
        pass