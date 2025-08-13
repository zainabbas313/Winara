from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, text
from decimal import Decimal
import json
from models.models import Bid, BidStatus, User, Team, Vertical, Receivable, ReceivableStatus
from interface.Irepositories.analytics_repository import IAnalyticsRepository
from utils.cache import redis_client
import logging

logger = logging.getLogger(__name__)


class AnalyticsRepository(IAnalyticsRepository):
    def __init__(self):
        pass

    def get_dashboard_kpis(self, db: Session, scope: str, team_id: Optional[UUID] = None,
                          user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                          date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get dashboard KPIs for specified scope and filters."""
        try:
            # Build base query
            query = db.query(Bid)
            
            # Apply scope filters
            if scope == "team" and team_id:
                query = query.filter(Bid.team_id == team_id)
            elif scope == "member" and user_id:
                query = query.filter(Bid.member_id == user_id)
            
            # Apply date filters
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            # Calculate KPIs
            total_bids = query.count()
            wins = query.filter(Bid.status == BidStatus.WON).count()
            
            # Calculate win rate
            win_rate = Decimal(wins) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
            
            # Calculate connect spend and revenue
            aggregates = query.with_entities(
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('connect_spend'),
                func.sum(Bid.total_cost).label('total_cost')
            ).first()
            
            connect_spend = aggregates.total_cost or Decimal('0')
            
            # Calculate revenue from won bids (estimated)
            won_bids = query.filter(Bid.status == BidStatus.WON).all()
            revenue = Decimal('0')
            
            for bid in won_bids:
                if bid.budget_type.value == 'fixed' and bid.budget_min:
                    revenue += bid.budget_min
                elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                    revenue += bid.hourly_rate * bid.estimated_hours
            
            # Calculate profit margin
            profit_margin = ((revenue - connect_spend) / revenue * 100) if revenue > 0 else Decimal('0')
            
            return {
                'total_bids': total_bids,
                'wins': wins,
                'win_rate': win_rate,
                'connect_spend': connect_spend,
                'revenue': revenue,
                'profit_margin': profit_margin
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard KPIs: {e}")
            return {}

    def get_bids_over_time(self, db: Session, team_id: Optional[UUID] = None,
                          user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                          date_to: Optional[date] = None, granularity: str = 'day') -> List[Dict[str, Any]]:
        """Get bids over time chart data."""
        try:
            # Build query with date grouping
            if granularity == 'day':
                date_field = func.date(Bid.submitted_at)
            elif granularity == 'week':
                date_field = func.date_trunc('week', Bid.submitted_at)
            elif granularity == 'month':
                date_field = func.date_trunc('month', Bid.submitted_at)
            else:
                date_field = func.date(Bid.submitted_at)
            
            query = db.query(
                date_field.label('date'),
                func.count(Bid.id).label('bids'),
                func.count(func.case((Bid.status == BidStatus.WON, 1))).label('wins')
            )
            
            # Apply filters
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if user_id:
                query = query.filter(Bid.member_id == user_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            results = query.group_by(date_field).order_by(date_field).all()
            
            return [
                {
                    'date': result.date.isoformat() if hasattr(result.date, 'isoformat') else str(result.date),
                    'bids': result.bids,
                    'wins': result.wins
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
        try:
            # For revenue, we'll use receivables data if available, otherwise estimate from won bids
            if granularity == 'day':
                date_field = func.date(Receivable.expected_payment_date)
            elif granularity == 'week':
                date_field = func.date_trunc('week', Receivable.expected_payment_date)
            elif granularity == 'month':
                date_field = func.date_trunc('month', Receivable.expected_payment_date)
            else:
                date_field = func.date(Receivable.expected_payment_date)
            
            query = db.query(
                date_field.label('date'),
                func.sum(Receivable.contract_value).label('revenue')
            ).join(Bid, Receivable.bid_id == Bid.id)
            
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
                    'date': result.date.isoformat() if hasattr(result.date, 'isoformat') else str(result.date),
                    'revenue': float(result.revenue or 0)
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
        try:
            query = db.query(
                Bid.vertical_id,
                Vertical.name.label('vertical_name'),
                func.count(Bid.id).label('bid_count'),
                func.count(func.case((Bid.status == BidStatus.WON, 1))).label('wins'),
                func.sum(Bid.total_cost).label('total_cost')
            ).join(Vertical, Bid.vertical_id == Vertical.id)
            
            # Apply filters
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if user_id:
                query = query.filter(Bid.member_id == user_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            results = query.group_by(Bid.vertical_id, Vertical.name).order_by(
                desc(func.count(Bid.id))
            ).all()
            
            # Calculate revenue for each vertical
            breakdown = []
            for result in results:
                # Get won bids for this vertical to calculate revenue
                won_bids = db.query(Bid).filter(
                    and_(
                        Bid.vertical_id == result.vertical_id,
                        Bid.status == BidStatus.WON
                    )
                )
                
                if team_id:
                    won_bids = won_bids.filter(Bid.team_id == team_id)
                if user_id:
                    won_bids = won_bids.filter(Bid.member_id == user_id)
                if date_from:
                    won_bids = won_bids.filter(Bid.submitted_at >= date_from)
                if date_to:
                    won_bids = won_bids.filter(Bid.submitted_at <= date_to)
                
                revenue = Decimal('0')
                for bid in won_bids.all():
                    if bid.budget_type.value == 'fixed' and bid.budget_min:
                        revenue += bid.budget_min
                    elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                        revenue += bid.hourly_rate * bid.estimated_hours
                
                win_rate = (result.wins / result.bid_count * 100) if result.bid_count > 0 else 0
                
                breakdown.append({
                    'vertical_id': result.vertical_id,
                    'name': result.vertical_name,
                    'wins': result.wins,
                    'revenue': revenue,
                    'bid_count': result.bid_count,
                    'win_rate': win_rate
                })
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error getting vertical breakdown: {e}")
            return []

    def get_team_performance(self, db: Session, date_from: Optional[date] = None,
                            date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get team performance comparison."""
        try:
            query = db.query(
                Bid.team_id,
                Team.name.label('team_name'),
                func.count(Bid.id).label('total_bids'),
                func.count(func.case((Bid.status == BidStatus.WON, 1))).label('wins'),
                func.sum(Bid.total_cost).label('connect_spend')
            ).join(Team, Bid.team_id == Team.id)
            
            # Apply date filters
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            results = query.group_by(Bid.team_id, Team.name).order_by(
                desc(func.count(func.case((Bid.status == BidStatus.WON, 1))))
            ).all()
            
            performance = []
            for result in results:
                # Calculate revenue and metrics
                won_bids = db.query(Bid).filter(
                    and_(
                        Bid.team_id == result.team_id,
                        Bid.status == BidStatus.WON
                    )
                )
                
                if date_from:
                    won_bids = won_bids.filter(Bid.submitted_at >= date_from)
                if date_to:
                    won_bids = won_bids.filter(Bid.submitted_at <= date_to)
                
                revenue = Decimal('0')
                for bid in won_bids.all():
                    if bid.budget_type.value == 'fixed' and bid.budget_min:
                        revenue += bid.budget_min
                    elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                        revenue += bid.hourly_rate * bid.estimated_hours
                
                win_rate = (result.wins / result.total_bids * 100) if result.total_bids > 0 else 0
                
                performance.append({
                    'team_id': result.team_id,
                    'team_name': result.team_name,
                    'total_bids': result.total_bids,
                    'wins': result.wins,
                    'win_rate': win_rate,
                    'revenue': revenue,
                    'connect_spend': result.connect_spend or Decimal('0')
                })
            
            return performance
            
        except Exception as e:
            logger.error(f"Error getting team performance: {e}")
            return []

    def get_member_performance(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get member performance data."""
        try:
            query = db.query(
                Bid.member_id,
                User.first_name,
                User.last_name,
                func.count(Bid.id).label('total_bids'),
                func.count(func.case((Bid.status == BidStatus.WON, 1))).label('wins'),
                func.sum(Bid.total_cost).label('connect_spend'),
                func.avg(Bid.connects_used).label('avg_connects_per_bid')
            ).join(User, Bid.member_id == User.id)
            
            # Apply filters
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            results = query.group_by(
                Bid.member_id, User.first_name, User.last_name
            ).order_by(desc(func.count(func.case((Bid.status == BidStatus.WON, 1))))).all()
            
            performance = []
            for result in results:
                # Calculate revenue and metrics
                won_bids = db.query(Bid).filter(
                    and_(
                        Bid.member_id == result.member_id,
                        Bid.status == BidStatus.WON
                    )
                )
                
                if team_id:
                    won_bids = won_bids.filter(Bid.team_id == team_id)
                if date_from:
                    won_bids = won_bids.filter(Bid.submitted_at >= date_from)
                if date_to:
                    won_bids = won_bids.filter(Bid.submitted_at <= date_to)
                
                revenue = Decimal('0')
                total_bid_value = Decimal('0')
                
                for bid in won_bids.all():
                    if bid.budget_type.value == 'fixed' and bid.budget_min:
                        revenue += bid.budget_min
                        total_bid_value += bid.budget_min
                    elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                        value = bid.hourly_rate * bid.estimated_hours
                        revenue += value
                        total_bid_value += value
                
                win_rate = (result.wins / result.total_bids * 100) if result.total_bids > 0 else 0
                avg_bid_value = total_bid_value / result.wins if result.wins > 0 else Decimal('0')
                
                performance.append({
                    'member_id': result.member_id,
                    'member_name': f"{result.first_name} {result.last_name}",
                    'total_bids': result.total_bids,
                    'wins': result.wins,
                    'win_rate': win_rate,
                    'revenue': revenue,
                    'connect_spend': result.connect_spend or Decimal('0'),
                    'avg_bid_value': avg_bid_value
                })
            
            return performance
            
        except Exception as e:
            logger.error(f"Error getting member performance: {e}")
            return []

    def get_bid_performance_report(self, db: Session, team_id: Optional[UUID] = None,
                                  date_from: Optional[date] = None,
                                  date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate bid performance report."""
        try:
            # Get summary KPIs
            summary = self.get_dashboard_kpis(db, "admin" if not team_id else "team", team_id, None, date_from, date_to)
            
            # Get team breakdown
            team_breakdown = self.get_team_performance(db, date_from, date_to)
            if team_id:
                team_breakdown = [t for t in team_breakdown if t['team_id'] == team_id]
            
            # Get member breakdown
            member_breakdown = self.get_member_performance(db, team_id, date_from, date_to)
            
            # Get vertical breakdown
            vertical_breakdown = self.get_vertical_breakdown(db, team_id, None, date_from, date_to)
            
            # Get trends
            trends = self.get_bids_over_time(db, team_id, None, date_from, date_to)
            
            return {
                'summary': summary,
                'team_breakdown': team_breakdown,
                'member_breakdown': member_breakdown,
                'vertical_breakdown': vertical_breakdown,
                'trends': trends
            }
            
        except Exception as e:
            logger.error(f"Error generating bid performance report: {e}")
            return {}

    def get_financial_report(self, db: Session, team_id: Optional[UUID] = None,
                            date_from: Optional[date] = None,
                            date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate financial report."""
        try:
            # Revenue analysis
            revenue_query = db.query(Receivable)
            if team_id:
                revenue_query = revenue_query.filter(Receivable.team_id == team_id)
            if date_from:
                revenue_query = revenue_query.filter(Receivable.expected_payment_date >= date_from)
            if date_to:
                revenue_query = revenue_query.filter(Receivable.expected_payment_date <= date_to)
            
            revenue_summary = revenue_query.with_entities(
                func.sum(Receivable.contract_value).label('total_expected'),
                func.sum(func.case((Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount))).label('total_received'),
                func.count(func.case((Receivable.status == ReceivableStatus.PENDING, 1))).label('pending_count'),
                func.sum(func.case((Receivable.status == ReceivableStatus.PENDING, Receivable.contract_value))).label('pending_value')
            ).first()
            
            # Cost analysis
            cost_query = db.query(Bid)
            if team_id:
                cost_query = cost_query.filter(Bid.team_id == team_id)
            if date_from:
                cost_query = cost_query.filter(Bid.submitted_at >= date_from)
            if date_to:
                cost_query = cost_query.filter(Bid.submitted_at <= date_to)
            
            cost_summary = cost_query.with_entities(
                func.sum(Bid.total_cost).label('total_connects_cost'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects_used')
            ).first()
            
            # Monthly trends
            monthly_trends = self.get_revenue_over_time(db, team_id, None, date_from, date_to, 'month')
            
            return {
                'revenue_summary': {
                    'total_expected': float(revenue_summary.total_expected or 0),
                    'total_received': float(revenue_summary.total_received or 0),
                    'pending_count': revenue_summary.pending_count or 0,
                    'pending_value': float(revenue_summary.pending_value or 0)
                },
                'cost_summary': {
                    'total_connects_cost': float(cost_summary.total_connects_cost or 0),
                    'total_connects_used': cost_summary.total_connects_used or 0
                },
                'profit_summary': {
                    'gross_profit': float((revenue_summary.total_received or 0) - (cost_summary.total_connects_cost or 0)),
                    'profit_margin': float(((revenue_summary.total_received or 0) - (cost_summary.total_connects_cost or 0)) / (revenue_summary.total_received or 1) * 100)
                },
                'monthly_trends': monthly_trends
            }
            
        except Exception as e:
            logger.error(f"Error generating financial report: {e}")
            return {}

    def get_operational_report(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None,
                              date_to: Optional[date] = None) -> Dict[str, Any]:
        """Generate operational report."""
        try:
            # Productivity metrics
            if team_id:
                team_count = 1
                member_count = db.query(User).filter(User.team_id == team_id).count()
            else:
                team_count = db.query(Team).count()
                member_count = db.query(User).filter(User.role.in_(['member', 'sub_admin'])).count()
            
            # Activity metrics
            query = db.query(Bid)
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            total_bids = query.count()
            
            # Calculate metrics
            days_in_period = (date_to - date_from).days if date_from and date_to else 30
            bids_per_day = total_bids / days_in_period if days_in_period > 0 else 0
            bids_per_member = total_bids / member_count if member_count > 0 else 0
            
            # Quality metrics
            quality_stats = query.with_entities(
                func.count(func.case((Bid.status == BidStatus.WON, 1))).label('wins'),
                func.count(func.case((Bid.status == BidStatus.DECLINED, 1))).label('declined'),
                func.avg(func.extract('days', Bid.last_status_change - Bid.submitted_at)).label('avg_response_time')
            ).first()
            
            return {
                'productivity_metrics': {
                    'total_teams': team_count,
                    'total_members': member_count,
                    'bids_per_day': round(bids_per_day, 2),
                    'bids_per_member': round(bids_per_member, 2)
                },
                'efficiency_metrics': {
                    'avg_response_time_days': float(quality_stats.avg_response_time or 0),
                    'win_rate': float((quality_stats.wins / total_bids * 100) if total_bids > 0 else 0),
                    'decline_rate': float((quality_stats.declined / total_bids * 100) if total_bids > 0 else 0)
                },
                'quality_metrics': {
                    'total_bids': total_bids,
                    'wins': quality_stats.wins or 0,
                    'declined': quality_stats.declined or 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating operational report: {e}")
            return {}

    def cache_analytics_data(self, key: str, data: Dict[str, Any], ttl_minutes: int = 15) -> None:
        """Cache analytics data."""
        try:
            redis_client.setex(key, ttl_minutes * 60, json.dumps(data, default=str))
        except Exception as e:
            logger.error(f"Error caching analytics data: {e}")

    def get_cached_analytics_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached analytics data."""
        try:
            cached_data = redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.error(f"Error getting cached analytics data: {e}")
            return None

    # Additional analytics methods for advanced insights

    def get_win_rate_trends(self, db: Session, team_id: Optional[UUID] = None,
                           user_id: Optional[UUID] = None, days: int = 30) -> List[Dict[str, Any]]:
        """Get win rate trends over time."""
        try:
            start_date = date.today() - timedelta(days=days)
            
            query = db.query(
                func.date(Bid.submitted_at).label('date'),
                func.count(Bid.id).label('total_bids'),
                func.count(func.case((Bid.status == BidStatus.WON, 1))).label('wins')
            ).filter(Bid.submitted_at >= start_date)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if user_id:
                query = query.filter(Bid.member_id == user_id)
            
            results = query.group_by(func.date(Bid.submitted_at)).order_by(func.date(Bid.submitted_at)).all()
            
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
        """Get cost analysis data."""
        try:
            query = db.query(Bid)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if user_id:
                query = query.filter(Bid.member_id == user_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            cost_stats = query.with_entities(
                func.sum(Bid.total_cost).label('total_cost'),
                func.sum(Bid.connects_used).label('regular_connects'),
                func.sum(Bid.boost_connects_used).label('boost_connects'),
                func.avg(Bid.total_cost).label('avg_cost_per_bid'),
                func.count(Bid.id).label('total_bids')
            ).first()
            
            # Calculate cost per win
            wins = query.filter(Bid.status == BidStatus.WON).count()
            cost_per_win = (cost_stats.total_cost / wins) if wins > 0 else 0
            
            return {
                'total_cost': float(cost_stats.total_cost or 0),
                'regular_connects': cost_stats.regular_connects or 0,
                'boost_connects': cost_stats.boost_connects or 0,
                'avg_cost_per_bid': float(cost_stats.avg_cost_per_bid or 0),
                'cost_per_win': float(cost_per_win),
                'total_bids': cost_stats.total_bids or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting cost analysis: {e}")
            return {}

    def get_roi_analysis(self, db: Session, team_id: Optional[UUID] = None,
                        user_id: Optional[UUID] = None, date_from: Optional[date] = None,
                        date_to: Optional[date] = None) -> Dict[str, Any]:
        """Get ROI analysis data."""
        try:
            # Get cost data
            cost_data = self.get_cost_analysis(db, team_id, user_id, date_from, date_to)
            
            # Get revenue data from won bids
            query = db.query(Bid).filter(Bid.status == BidStatus.WON)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if user_id:
                query = query.filter(Bid.member_id == user_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            won_bids = query.all()
            total_revenue = Decimal('0')
            
            for bid in won_bids:
                if bid.budget_type.value == 'fixed' and bid.budget_min:
                    total_revenue += bid.budget_min
                elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                    total_revenue += bid.hourly_rate * bid.estimated_hours
            
            total_cost = Decimal(str(cost_data['total_cost']))
            roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
            
            return {
                'total_revenue': float(total_revenue),
                'total_cost': float(total_cost),
                'net_profit': float(total_revenue - total_cost),
                'roi_percentage': float(roi),
                'revenue_per_bid': float(total_revenue / cost_data['total_bids']) if cost_data['total_bids'] > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting ROI analysis: {e}")
            return {}