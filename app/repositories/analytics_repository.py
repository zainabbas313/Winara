# repositories/analytics_repository.py
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, text, case
from decimal import Decimal
import json
import redis
import logging
from contextlib import contextmanager

from models.models import (
    Bid, BidStatus, User, Team, Vertical, Receivable, ReceivableStatus,
    UserRole, BudgetType
)
from interface.Irepositories.analytics_repository import IAnalyticsRepository
from core.config.config import settings

logger = logging.getLogger(__name__)


class AnalyticsRepository(IAnalyticsRepository):
    def __init__(self):
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL) if settings.REDIS_URL else None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.redis_client = None

    @contextmanager
    def db_error_handler(self):
        """Context manager for database error handling."""
        try:
            yield
        except Exception as e:
            logger.error(f"Database error in analytics repository: {e}")
            raise

    def get_dashboard_kpis(self, db: Session, scope: str, team_id: Optional[UUID] = None,
                          user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                          date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get dashboard KPIs for specified scope and filters."""
        with self.db_error_handler():
            try:
                # Build base query with proper joins
                query = db.query(Bid).join(User, Bid.member_id == User.id, isouter=True)
                
                # Apply scope filters
                if scope == "team" and team_id:
                    query = query.filter(Bid.team_id == team_id)
                elif scope == "member" and user_id:
                    query = query.filter(Bid.member_id == user_id)
                
                # Apply date filters
                if date_from:
                    query = query.filter(Bid.submitted_at >= date_from)
                if date_to:
                    query = query.filter(Bid.submitted_at <= date_to + timedelta(days=1))
                
                # Calculate KPIs with proper aggregation
                total_bids = query.count()
                
                if total_bids == 0:
                    return self._empty_kpis()
                
                wins = query.filter(Bid.status == BidStatus.WON).count()
                
                # Calculate win rate
                win_rate = Decimal(wins) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
                
                # Calculate connect spend
                cost_aggregates = query.with_entities(
                    func.sum(func.coalesce(Bid.total_cost, 0)).label('total_cost'),
                    func.sum(func.coalesce(Bid.connects_used, 0) + 
                            func.coalesce(Bid.boost_connects_used, 0)).label('total_connects')
                ).first()
                
                connect_spend = cost_aggregates.total_cost or Decimal('0')
                total_connects = cost_aggregates.total_connects or 0
                
                # Calculate revenue from won bids
                revenue = self._calculate_revenue_from_bids(
                    query.filter(Bid.status == BidStatus.WON).all()
                )
                
                # Calculate profit margin
                profit_margin = self._calculate_profit_margin(revenue, connect_spend)
                
                return {
                    'total_bids': total_bids,
                    'wins': wins,
                    'win_rate': win_rate,
                    'connect_spend': connect_spend,
                    'revenue': revenue,
                    'profit_margin': profit_margin,
                    'total_connects': total_connects,
                    'avg_cost_per_bid': connect_spend / total_bids if total_bids > 0 else Decimal('0'),
                    'cost_per_win': connect_spend / wins if wins > 0 else Decimal('0')
                }
                
            except Exception as e:
                logger.error(f"Error getting dashboard KPIs: {e}")
                return self._empty_kpis()

    def get_bids_over_time(self, db: Session, team_id: Optional[UUID] = None,
                          user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                          date_to: Optional[date] = None, granularity: str = 'day') -> List[Dict[str, Any]]:
        """Get bids over time chart data."""
        with self.db_error_handler():
            try:
                # Define date field based on granularity
                date_field = self._get_date_field(granularity)
                
                query = db.query(
                    date_field.label('date'),
                    func.count(Bid.id).label('bids'),
                    func.count(case((Bid.status == BidStatus.WON, 1))).label('wins'),
                    func.count(case((Bid.status == BidStatus.DECLINED, 1))).label('declined')
                )
                
                # Apply filters
                query = self._apply_base_filters(query, team_id, user_id, date_from, date_to)
                
                results = query.group_by(date_field).order_by(date_field).all()
                
                return [
                    {
                        'date': self._format_date(result.date, granularity),
                        'bids': result.bids,
                        'wins': result.wins,
                        'declined': result.declined,
                        'win_rate': (result.wins / result.bids * 100) if result.bids > 0 else 0
                    }
                    for result in results
                ]
                
            except Exception as e:
                logger.error(f"Error getting bids over time: {e}")
                return []

    def get_revenue_over_time(self, db: Session, team_id: Optional[UUID] = None,
                             user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                             date_to: Optional[date] = None, granularity: str = 'day') -> List[Dict[str, Any]]:
        """Get revenue over time chart data."""
        with self.db_error_handler():
            try:
                date_field = self._get_date_field(granularity, Receivable.expected_payment_date)
                
                query = db.query(
                    date_field.label('date'),
                    func.sum(func.coalesce(Receivable.contract_value, 0)).label('expected_revenue'),
                    func.sum(case((Receivable.status == ReceivableStatus.PAID, 
                                 Receivable.payment_amount), else_=0)).label('actual_revenue'),
                    func.count(Receivable.id).label('receivable_count')
                ).select_from(Receivable).join(Bid, Receivable.bid_id == Bid.id)
                
                # Apply filters
                if team_id:
                    query = query.filter(Receivable.team_id == team_id)
                if user_id:
                    query = query.filter(Bid.member_id == user_id)
                if date_from:
                    query = query.filter(Receivable.expected_payment_date >= date_from)
                if date_to:
                    query = query.filter(Receivable.expected_payment_date <= date_to)
                
                results = query.group_by(date_field).order_by(date_field).all()
                
                return [
                    {
                        'date': self._format_date(result.date, granularity),
                        'expected_revenue': float(result.expected_revenue or 0),
                        'actual_revenue': float(result.actual_revenue or 0),
                        'receivable_count': result.receivable_count
                    }
                    for result in results
                ]
                
            except Exception as e:
                logger.error(f"Error getting revenue over time: {e}")
                return []

    def get_vertical_breakdown(self, db: Session, team_id: Optional[UUID] = None,
                              user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get vertical performance breakdown."""
        with self.db_error_handler():
            try:
                query = db.query(
                    Bid.vertical_id,
                    Vertical.name.label('vertical_name'),
                    func.count(Bid.id).label('bid_count'),
                    func.count(case((Bid.status == BidStatus.WON, 1))).label('wins'),
                    func.sum(func.coalesce(Bid.total_cost, 0)).label('total_cost'),
                    func.avg(func.coalesce(Bid.connects_used, 0)).label('avg_connects_per_bid')
                ).join(Vertical, Bid.vertical_id == Vertical.id)
                
                # Apply filters
                query = self._apply_base_filters(query, team_id, user_id, date_from, date_to)
                
                results = query.group_by(
                    Bid.vertical_id, Vertical.name
                ).order_by(desc(func.count(Bid.id))).all()
                
                breakdown = []
                for result in results:
                    revenue = self._calculate_vertical_revenue(
                        db, result.vertical_id, team_id, user_id, date_from, date_to
                    )
                    
                    win_rate = (result.wins / result.bid_count * 100) if result.bid_count > 0 else 0
                    
                    breakdown.append({
                        'vertical_id': result.vertical_id,
                        'name': result.vertical_name,
                        'wins': result.wins,
                        'revenue': revenue,
                        'bid_count': result.bid_count,
                        'win_rate': win_rate,
                        'total_cost': result.total_cost or Decimal('0'),
                        'avg_connects_per_bid': float(result.avg_connects_per_bid or 0)
                    })
                
                return breakdown
                
            except Exception as e:
                logger.error(f"Error getting vertical breakdown: {e}")
                return []

    def get_team_performance(self, db: Session, date_from: Optional[date] = None,
                            date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get team performance comparison."""
        with self.db_error_handler():
            try:
                query = db.query(
                    Bid.team_id,
                    Team.name.label('team_name'),
                    func.count(Bid.id).label('total_bids'),
                    func.count(case((Bid.status == BidStatus.WON, 1))).label('wins'),
                    func.sum(func.coalesce(Bid.total_cost, 0)).label('connect_spend'),
                    func.count(func.distinct(Bid.member_id)).label('active_members')
                ).join(Team, Bid.team_id == Team.id)
                
                # Apply date filters
                if date_from:
                    query = query.filter(Bid.submitted_at >= date_from)
                if date_to:
                    query = query.filter(Bid.submitted_at <= date_to + timedelta(days=1))
                
                results = query.group_by(
                    Bid.team_id, Team.name
                ).order_by(desc(func.count(case((Bid.status == BidStatus.WON, 1))))).all()
                
                performance = []
                for result in results:
                    revenue = self._calculate_team_revenue(
                        db, result.team_id, date_from, date_to
                    )
                    
                    win_rate = (result.wins / result.total_bids * 100) if result.total_bids > 0 else 0
                    
                    performance.append({
                        'team_id': result.team_id,
                        'team_name': result.team_name,
                        'total_bids': result.total_bids,
                        'wins': result.wins,
                        'win_rate': win_rate,
                        'revenue': revenue,
                        'connect_spend': result.connect_spend or Decimal('0'),
                        'active_members': result.active_members,
                        'bids_per_member': result.total_bids / result.active_members if result.active_members > 0 else 0
                    })
                
                return performance
                
            except Exception as e:
                logger.error(f"Error getting team performance: {e}")
                return []

    def get_member_performance(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get member performance data."""
        with self.db_error_handler():
            try:
                query = db.query(
                    Bid.member_id,
                    User.first_name,
                    User.last_name,
                    User.email,
                    func.count(Bid.id).label('total_bids'),
                    func.count(case((Bid.status == BidStatus.WON, 1))).label('wins'),
                    func.sum(func.coalesce(Bid.total_cost, 0)).label('connect_spend'),
                    func.avg(func.coalesce(Bid.connects_used, 0)).label('avg_connects_per_bid'),
                    func.max(Bid.submitted_at).label('last_bid_date')
                ).join(User, Bid.member_id == User.id)
                
                # Apply filters
                if team_id:
                    query = query.filter(Bid.team_id == team_id)
                if date_from:
                    query = query.filter(Bid.submitted_at >= date_from)
                if date_to:
                    query = query.filter(Bid.submitted_at <= date_to + timedelta(days=1))
                
                results = query.group_by(
                    Bid.member_id, User.first_name, User.last_name, User.email
                ).order_by(desc(func.count(case((Bid.status == BidStatus.WON, 1))))).all()
                
                performance = []
                for result in results:
                    revenue = self._calculate_member_revenue(
                        db, result.member_id, team_id, date_from, date_to
                    )
                    
                    win_rate = (result.wins / result.total_bids * 100) if result.total_bids > 0 else 0
                    avg_bid_value = revenue / result.wins if result.wins > 0 else Decimal('0')
                    
                    performance.append({
                        'member_id': result.member_id,
                        'member_name': f"{result.first_name or ''} {result.last_name or ''}".strip(),
                        'email': result.email,
                        'total_bids': result.total_bids,
                        'wins': result.wins,
                        'win_rate': win_rate,
                        'revenue': revenue,
                        'connect_spend': result.connect_spend or Decimal('0'),
                        'avg_bid_value': avg_bid_value,
                        'avg_connects_per_bid': float(result.avg_connects_per_bid or 0),
                        'last_bid_date': result.last_bid_date
                    })
                
                return performance
                
            except Exception as e:
                logger.error(f"Error getting member performance: {e}")
                return []

    def get_bid_performance_report(self, db: Session, team_id: Optional[UUID] = None,
                                  date_from: Optional[date] = None,
                                  date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate comprehensive bid performance report."""
        with self.db_error_handler():
            try:
                # Get summary KPIs
                summary = self.get_dashboard_kpis(
                    db, "admin" if not team_id else "team", team_id, None, date_from, date_to
                )
                
                # Get breakdowns
                team_breakdown = self.get_team_performance(db, date_from, date_to)
                if team_id:
                    team_breakdown = [t for t in team_breakdown if t['team_id'] == team_id]
                
                member_breakdown = self.get_member_performance(db, team_id, date_from, date_to)
                vertical_breakdown = self.get_vertical_breakdown(db, team_id, None, date_from, date_to)
                trends = self.get_bids_over_time(db, team_id, None, date_from, date_to)
                
                # Additional metrics
                status_distribution = self._get_bid_status_distribution(db, team_id, date_from, date_to)
                monthly_comparison = self._get_monthly_comparison(db, team_id, date_from, date_to)
                
                return {
                    'summary': summary,
                    'team_breakdown': team_breakdown,
                    'member_breakdown': member_breakdown,
                    'vertical_breakdown': vertical_breakdown,
                    'trends': trends,
                    'status_distribution': status_distribution,
                    'monthly_comparison': monthly_comparison
                }
                
            except Exception as e:
                logger.error(f"Error generating bid performance report: {e}")
                return {}

    def get_financial_report(self, db: Session, team_id: Optional[UUID] = None,
                            date_from: Optional[date] = None,
                            date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate comprehensive financial report."""
        with self.db_error_handler():
            try:
                # Revenue analysis from receivables
                revenue_query = db.query(Receivable)
                if team_id:
                    revenue_query = revenue_query.filter(Receivable.team_id == team_id)
                if date_from:
                    revenue_query = revenue_query.filter(Receivable.expected_payment_date >= date_from)
                if date_to:
                    revenue_query = revenue_query.filter(Receivable.expected_payment_date <= date_to)
                
                revenue_summary = revenue_query.with_entities(
                    func.sum(func.coalesce(Receivable.contract_value, 0)).label('total_expected'),
                    func.sum(case((Receivable.status == ReceivableStatus.PAID, 
                                 Receivable.payment_amount), else_=0)).label('total_received'),
                    func.count(case((Receivable.status == ReceivableStatus.PENDING, 1))).label('pending_count'),
                    func.sum(case((Receivable.status == ReceivableStatus.PENDING, 
                                 Receivable.contract_value), else_=0)).label('pending_value'),
                    func.count(case((Receivable.status == ReceivableStatus.OVERDUE, 1))).label('overdue_count'),
                    func.sum(case((Receivable.status == ReceivableStatus.OVERDUE, 
                                 Receivable.contract_value), else_=0)).label('overdue_value')
                ).first()
                
                # Cost analysis
                cost_summary = self.get_cost_analysis(db, team_id, None, date_from, date_to)
                
                # Calculate profit metrics
                total_received = float(revenue_summary.total_received or 0)
                total_cost = float(cost_summary.get('total_cost', 0))
                
                profit_summary = {
                    'gross_profit': total_received - total_cost,
                    'profit_margin': ((total_received - total_cost) / total_received * 100) if total_received > 0 else 0,
                    'net_profit': total_received - total_cost,  # Simplified for this example
                    'roi_percentage': ((total_received - total_cost) / total_cost * 100) if total_cost > 0 else 0
                }
                
                # Monthly trends
                monthly_trends = self.get_revenue_over_time(db, team_id, None, date_from, date_to, 'month')
                
                # Receivables aging
                receivables_aging = self._get_receivables_aging(db, team_id)
                
                return {
                    'revenue_summary': {
                        'total_expected': float(revenue_summary.total_expected or 0),
                        'total_received': total_received,
                        'pending_count': revenue_summary.pending_count or 0,
                        'pending_value': float(revenue_summary.pending_value or 0),
                        'overdue_count': revenue_summary.overdue_count or 0,
                        'overdue_value': float(revenue_summary.overdue_value or 0)
                    },
                    'cost_summary': cost_summary,
                    'profit_summary': profit_summary,
                    'monthly_trends': monthly_trends,
                    'receivables_aging': receivables_aging
                }
                
            except Exception as e:
                logger.error(f"Error generating financial report: {e}")
                return {}

    def get_operational_report(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate operational efficiency report."""
        with self.db_error_handler():
            try:
                # Team and member counts
                if team_id:
                    team_count = 1
                    member_count = db.query(User).filter(
                        User.team_id == team_id,
                        User.role == UserRole.MEMBER,
                        User.is_active == True
                    ).count()
                else:
                    team_count = db.query(Team).count()
                    member_count = db.query(User).filter(
                        User.role.in_([UserRole.MEMBER, UserRole.SUB_ADMIN]),
                        User.is_active == True
                    ).count()
                
                # Activity metrics
                query = db.query(Bid)
                if team_id:
                    query = query.filter(Bid.team_id == team_id)
                if date_from:
                    query = query.filter(Bid.submitted_at >= date_from)
                if date_to:
                    query = query.filter(Bid.submitted_at <= date_to + timedelta(days=1))
                
                total_bids = query.count()
                active_members = query.with_entities(
                    func.count(func.distinct(Bid.member_id))
                ).scalar()
                
                # Calculate periods
                days_in_period = self._calculate_days_in_period(date_from, date_to)
                bids_per_day = total_bids / days_in_period if days_in_period > 0 else 0
                bids_per_member = total_bids / member_count if member_count > 0 else 0
                
                # Quality and efficiency metrics
                quality_stats = query.with_entities(
                    func.count(case((Bid.status == BidStatus.WON, 1))).label('wins'),
                    func.count(case((Bid.status == BidStatus.DECLINED, 1))).label('declined'),
                    func.count(case((Bid.status == BidStatus.RESPONDED, 1))).label('responded'),
                    func.avg(func.extract('days', 
                             func.coalesce(Bid.last_status_change, Bid.submitted_at) - Bid.submitted_at)
                            ).label('avg_response_time')
                ).first()
                
                # Team utilization
                team_performance = self.get_team_performance(db, date_from, date_to)
                if team_id:
                    team_performance = [t for t in team_performance if t['team_id'] == team_id]
                
                return {
                    'productivity_metrics': {
                        'total_teams': team_count,
                        'total_members': member_count,
                        'active_members': active_members or 0,
                        'bids_per_day': round(bids_per_day, 2),
                        'bids_per_member': round(bids_per_member, 2)
                    },
                    'efficiency_metrics': {
                        'avg_response_time_days': float(quality_stats.avg_response_time or 0),
                        'win_rate': float((quality_stats.wins / total_bids * 100) if total_bids > 0 else 0),
                        'decline_rate': float((quality_stats.declined / total_bids * 100) if total_bids > 0 else 0),
                        'conversion_rate': float((quality_stats.responded / total_bids * 100) if total_bids > 0 else 0)
                    },
                    'quality_metrics': {
                        'total_bids': total_bids,
                        'wins': quality_stats.wins or 0,
                        'declined': quality_stats.declined or 0,
                        'quality_score': self._calculate_quality_score(quality_stats, total_bids)
                    },
                    'team_utilization': team_performance
                }
                
            except Exception as e:
                logger.error(f"Error generating operational report: {e}")
                return {}

    # Cache methods
    def cache_analytics_data(self, key: str, data: Dict[str, Any], ttl_minutes: int = 15) -> None:
        """Cache analytics data with Redis."""
        if not self.redis_client:
            return
            
        try:
            self.redis_client.setex(key, ttl_minutes * 60, json.dumps(data, default=str))
        except Exception as e:
            logger.error(f"Error caching analytics data: {e}")

    def get_cached_analytics_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached analytics data from Redis."""
        if not self.redis_client:
            return None
            
        try:
            cached_data = self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.error(f"Error getting cached analytics data: {e}")
            return None

    # Additional analytics methods
    def get_win_rate_trends(self, db: Session, team_id: Optional[UUID] = None,
                           user_id: Optional[UUID] = None, days: int = 30) -> List[Dict[str, Any]]:
        """Get win rate trends over specified period."""
        with self.db_error_handler():
            try:
                start_date = date.today() - timedelta(days=days)
                
                query = db.query(
                    func.date(Bid.submitted_at).label('date'),
                    func.count(Bid.id).label('total_bids'),
                    func.count(case((Bid.status == BidStatus.WON, 1))).label('wins')
                ).filter(Bid.submitted_at >= start_date)
                
                query = self._apply_base_filters(query, team_id, user_id)
                
                results = query.group_by(func.date(Bid.submitted_at))\
                              .order_by(func.date(Bid.submitted_at)).all()
                
                return [
                    {
                        'date': result.date.isoformat(),
                        'win_rate': (result.wins / result.total_bids * 100) if result.total_bids > 0 else 0,
                        'total_bids': result.total_bids,
                        'wins': result.wins
                    }
                    for result in results
                ]
                
            except Exception as e:
                logger.error(f"Error getting win rate trends: {e}")
                return []

    def get_cost_analysis(self, db: Session, team_id: Optional[UUID] = None,
                         user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                         date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get detailed cost analysis."""
        with self.db_error_handler():
            try:
                query = db.query(Bid)
                query = self._apply_base_filters(query, team_id, user_id, date_from, date_to)
                
                cost_stats = query.with_entities(
                    func.sum(func.coalesce(Bid.total_cost, 0)).label('total_cost'),
                    func.sum(func.coalesce(Bid.connects_used, 0)).label('regular_connects'),
                    func.sum(func.coalesce(Bid.boost_connects_used, 0)).label('boost_connects'),
                    func.avg(func.coalesce(Bid.total_cost, 0)).label('avg_cost_per_bid'),
                    func.count(Bid.id).label('total_bids')
                ).first()
                
                wins = query.filter(Bid.status == BidStatus.WON).count()
                cost_per_win = (cost_stats.total_cost / wins) if wins > 0 else 0
                
                return {
                    'total_cost': float(cost_stats.total_cost or 0),
                    'regular_connects': cost_stats.regular_connects or 0,
                    'boost_connects': cost_stats.boost_connects or 0,
                    'avg_cost_per_bid': float(cost_stats.avg_cost_per_bid or 0),
                    'cost_per_win': float(cost_per_win),
                    'total_bids': cost_stats.total_bids or 0,
                    'total_connects_used': (cost_stats.regular_connects or 0) + (cost_stats.boost_connects or 0)
                }
                
            except Exception as e:
                logger.error(f"Error getting cost analysis: {e}")
                return {}

    def get_roi_analysis(self, db: Session, team_id: Optional[UUID] = None,
                        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                        date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get return on investment analysis."""
        with self.db_error_handler():
            try:
                cost_data = self.get_cost_analysis(db, team_id, user_id, date_from, date_to)
                
                query = db.query(Bid).filter(Bid.status == BidStatus.WON)
                query = self._apply_base_filters(query, team_id, user_id, date_from, date_to)
                
                won_bids = query.all()
                total_revenue = self._calculate_revenue_from_bids(won_bids)
                
                total_cost = Decimal(str(cost_data['total_cost']))
                roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
                
                return {
                    'total_revenue': float(total_revenue),
                    'total_cost': float(total_cost),
                    'net_profit': float(total_revenue - total_cost),
                    'roi_percentage': float(roi),
                    'revenue_per_bid': float(total_revenue / cost_data['total_bids']) if cost_data['total_bids'] > 0 else 0,
                    'profit_per_bid': float((total_revenue - total_cost) / cost_data['total_bids']) if cost_data['total_bids'] > 0 else 0
                }
                
            except Exception as e:
                logger.error(f"Error getting ROI analysis: {e}")
                return {}

    # Helper methods
    def _empty_kpis(self) -> Dict[str, Any]:
        """Return empty KPI structure."""
        return {
            'total_bids': 0,
            'wins': 0,
            'win_rate': Decimal('0'),
            'connect_spend': Decimal('0'),
            'revenue': Decimal('0'),
            'profit_margin': Decimal('0'),
            'total_connects': 0,
            'avg_cost_per_bid': Decimal('0'),
            'cost_per_win': Decimal('0')
        }

    def _get_date_field(self, granularity: str, date_column=None):
        """Get appropriate date field based on granularity."""
        if date_column is None:
            date_column = Bid.submitted_at
            
        if granularity == 'day':
            return func.date(date_column)
        elif granularity == 'week':
            return func.date_trunc('week', date_column)
        elif granularity == 'month':
            return func.date_trunc('month', date_column)
        else:
            return func.date(date_column)

    def _format_date(self, date_obj, granularity: str) -> str:
        """Format date based on granularity."""
        if hasattr(date_obj, 'isoformat'):
            return date_obj.isoformat()
        return str(date_obj)

    def _apply_base_filters(self, query, team_id: Optional[UUID] = None,
                           user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                           date_to: Optional[date] = None):
        """Apply common filters to queries."""
        if team_id:
            query = query.filter(Bid.team_id == team_id)
        if user_id:
            query = query.filter(Bid.member_id == user_id)
        if date_from:
            query = query.filter(Bid.submitted_at >= date_from)
        if date_to:
            query = query.filter(Bid.submitted_at <= date_to + timedelta(days=1))
        return query

    def _calculate_revenue_from_bids(self, bids: List[Bid]) -> Decimal:
        """Calculate total revenue from a list of bids."""
        total_revenue = Decimal('0')
        for bid in bids:
            if bid.budget_type == BudgetType.FIXED and bid.budget_min:
                total_revenue += bid.budget_min
            elif bid.budget_type == BudgetType.HOURLY and bid.hourly_rate and bid.estimated_hours:
                total_revenue += bid.hourly_rate * bid.estimated_hours
        return total_revenue

    def _calculate_profit_margin(self, revenue: Decimal, cost: Decimal) -> Decimal:
        """Calculate profit margin percentage."""
        if revenue > 0:
            return ((revenue - cost) / revenue * 100)
        return Decimal('0')

    def _calculate_vertical_revenue(self, db: Session, vertical_id: UUID, 
                                   team_id: Optional[UUID] = None, user_id: Optional[UUID] = None,
                                   date_from: Optional[date] = None, date_to: Optional[date] = None) -> Decimal:
        """Calculate revenue for a specific vertical."""
        query = db.query(Bid).filter(
            and_(Bid.vertical_id == vertical_id, Bid.status == BidStatus.WON)
        )
        query = self._apply_base_filters(query, team_id, user_id, date_from, date_to)
        won_bids = query.all()
        return self._calculate_revenue_from_bids(won_bids)

    def _calculate_team_revenue(self, db: Session, team_id: UUID,
                               date_from: Optional[date] = None, date_to: Optional[date] = None) -> Decimal:
        """Calculate revenue for a specific team."""
        query = db.query(Bid).filter(
            and_(Bid.team_id == team_id, Bid.status == BidStatus.WON)
        )
        query = self._apply_base_filters(query, date_from=date_from, date_to=date_to)
        won_bids = query.all()
        return self._calculate_revenue_from_bids(won_bids)

    def _calculate_member_revenue(self, db: Session, member_id: UUID, team_id: Optional[UUID] = None,
                                 date_from: Optional[date] = None, date_to: Optional[date] = None) -> Decimal:
        """Calculate revenue for a specific member."""
        query = db.query(Bid).filter(
            and_(Bid.member_id == member_id, Bid.status == BidStatus.WON)
        )
        query = self._apply_base_filters(query, team_id, date_from=date_from, date_to=date_to)
        won_bids = query.all()
        return self._calculate_revenue_from_bids(won_bids)

    def _calculate_days_in_period(self, date_from: Optional[date], date_to: Optional[date]) -> int:
        """Calculate number of days in the specified period."""
        if date_from and date_to:
            return (date_to - date_from).days + 1
        elif date_from:
            return (date.today() - date_from).days + 1
        elif date_to:
            return (date_to - date.today()).days + 1
        return 30  # Default period

    def _get_bid_status_distribution(self, db: Session, team_id: Optional[UUID] = None,
                                    date_from: Optional[date] = None, date_to: Optional[date] = None) -> Dict[str, int]:
        """Get distribution of bid statuses."""
        query = db.query(
            Bid.status,
            func.count(Bid.id).label('count')
        )
        query = self._apply_base_filters(query, team_id, date_from=date_from, date_to=date_to)
        
        results = query.group_by(Bid.status).all()
        return {result.status.value: result.count for result in results}

    def _get_monthly_comparison(self, db: Session, team_id: Optional[UUID] = None,
                               date_from: Optional[date] = None, date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get monthly comparison data."""
        current_month = date.today().replace(day=1)
        prev_month = (current_month - timedelta(days=1)).replace(day=1)
        
        current_data = self.get_dashboard_kpis(
            db, "team" if team_id else "admin", team_id, None, current_month, date.today()
        )
        prev_data = self.get_dashboard_kpis(
            db, "team" if team_id else "admin", team_id, None, prev_month, current_month - timedelta(days=1)
        )
        
        return {
            'current_month': current_data,
            'previous_month': prev_data,
            'growth_rates': {
                'bids': self._calculate_growth_rate(current_data['total_bids'], prev_data['total_bids']),
                'wins': self._calculate_growth_rate(current_data['wins'], prev_data['wins']),
                'revenue': float(self._calculate_growth_rate(float(current_data['revenue']), float(prev_data['revenue'])))
            }
        }

    def _get_receivables_aging(self, db: Session, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get receivables aging analysis."""
        today = date.today()
        
        query = db.query(Receivable)
        if team_id:
            query = query.filter(Receivable.team_id == team_id)
        
        aging_buckets = query.with_entities(
            func.count(case((Receivable.expected_payment_date >= today, 1))).label('current'),
            func.count(case((and_(Receivable.expected_payment_date < today, 
                                 Receivable.expected_payment_date >= today - timedelta(days=30)), 1))).label('overdue_30'),
            func.count(case((and_(Receivable.expected_payment_date < today - timedelta(days=30),
                                 Receivable.expected_payment_date >= today - timedelta(days=60)), 1))).label('overdue_60'),
            func.count(case((Receivable.expected_payment_date < today - timedelta(days=60), 1))).label('overdue_60_plus')
        ).first()
        
        return {
            'current': aging_buckets.current or 0,
            'overdue_30': aging_buckets.overdue_30 or 0,
            'overdue_60': aging_buckets.overdue_60 or 0,
            'overdue_60_plus': aging_buckets.overdue_60_plus or 0
        }

    def _calculate_quality_score(self, quality_stats, total_bids: int) -> float:
        """Calculate quality score based on various metrics."""
        if total_bids == 0:
            return 0.0
            
        win_rate = (quality_stats.wins or 0) / total_bids
        response_rate = (quality_stats.responded or 0) / total_bids
        decline_rate = (quality_stats.declined or 0) / total_bids
        
        # Simple quality scoring algorithm (can be enhanced)
        quality_score = (win_rate * 5) + (response_rate * 3) - (decline_rate * 2)
        return min(10.0, max(0.0, quality_score * 10))

    def _calculate_growth_rate(self, current: float, previous: float) -> float:
        """Calculate growth rate percentage."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100