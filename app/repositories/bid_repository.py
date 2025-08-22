from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc, case, cast, Date
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Bid, BidStatus, User, Team, Vertical, UserRole
from schemas.bid import (
    BidCreate, BidUpdate, BidListFilter, EnhancedBidFilter,
    TeamBidStats, MemberBidRanking, EarningsResponse, BidAnalytics,
    MemberRankingFilter, BulkOperationResult, MonthlyTrend,
    VerticalEarnings, TeamEarnings, MemberEarnings, BidSortField, SortDirection
)
from schemas.common import PaginatedResponse
from interface.Irepositories.bid_repository import IBidRepository
from utils.helpers import calculate_connect_cost, estimate_project_value, can_edit_bid
from utils.sort_values import _apply_bid_filters, _apply_enhanced_filters, _apply_enhanced_sorting, _apply_sorting_bid
import logging

logger = logging.getLogger(__name__)


class BidRepository(BaseRepository[Bid], IBidRepository):
    def __init__(self):
        super().__init__(Bid)

    def create(self, db: Session, bid_data: BidCreate) -> Bid:
        """Create a new bid."""
        try:
            connect_cost = calculate_connect_cost(
                bid_data.connects_used, 
                bid_data.boost_connects_used
            )
            total_cost = connect_cost
            
            bid_dict = bid_data.dict()
            bid_dict.update({
                'connect_cost': connect_cost,
                'total_cost': total_cost,
                'submitted_at': datetime.utcnow(),
                'last_status_change': datetime.utcnow()
            })
            
            return super().create(db, **bid_dict)
        except Exception as e:
            logger.error(f"Error creating bid: {e}")
            raise

    def get_by_id(self, db: Session, bid_id: UUID) -> Optional[Bid]:
        """Get bid by ID with related data."""
        try:
            return db.query(Bid).options(
                joinedload(Bid.member),
                joinedload(Bid.team),
                joinedload(Bid.vertical)
            ).filter(Bid.id == bid_id).first()
        except Exception as e:
            logger.error(f"Error getting bid {bid_id}: {e}")
            return None

    def get_all(self, db: Session, filters: BidListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-submitted_at") -> PaginatedResponse:
        """Get all bids with filters and pagination."""
        try:
            query = db.query(Bid).options(
                joinedload(Bid.member),
                joinedload(Bid.team),
                joinedload(Bid.vertical)
            )
            
            # Apply filters
            query = _apply_bid_filters(query, filters)
            # Apply enhanced filters  
            # query = _apply_enhanced_filters(query, filters)
            
            # Apply sorting using the fixed function
            query = _apply_sorting_bid(query, sort_by, Bid)
            
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
            logger.error(f"Error getting bids: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_bids_by_role(self, db: Session, filters: EnhancedBidFilter, 
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None,
                        skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get bids based on user role with enhanced filtering."""
        try:
            query = db.query(Bid).options(
                joinedload(Bid.member),
                joinedload(Bid.team),
                joinedload(Bid.vertical)
            )
            
            # Apply role-based filters
            if requesting_user_role == UserRole.MEMBER:
                query = query.filter(Bid.member_id == requesting_user_id)
            elif requesting_user_role == UserRole.SUB_ADMIN:
                query = query.filter(Bid.team_id == requesting_user_team_id)
            
            # Apply enhanced filters
            query = _apply_enhanced_filters(query, filters)
            
            # Apply sorting
            if filters.sort_field and filters.sort_direction:
                query = _apply_enhanced_sorting(query, filters.sort_field, filters.sort_direction)
            else:
                query = _apply_sorting_bid(query, "-submitted_at", Bid)
            
            total_count = query.count()
            items = query.offset(skip).limit(limit).all()
            
            next_cursor = None
            if len(items) == limit and skip + limit < total_count:
                next_cursor = f"offset:{skip + limit}"
            
            return PaginatedResponse(
                items=items,
                next_cursor=next_cursor,
                count=total_count
            )
        except Exception as e:
            logger.error(f"Error getting bids by role: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)
        
    def can_access_bid(self, db: Session, bid_id: UUID, user_id: UUID, 
                      user_role: UserRole, user_team_id: Optional[UUID] = None) -> bool:
        """Check if user can access specific bid."""
        try:
            bid = self.get_by_id(db, bid_id)
            if not bid:
                logger.error(f"Bid not found")
                return False
            
            if user_role == UserRole.ADMIN:
                return True
            elif user_role == UserRole.SUB_ADMIN:
                return bid.team_id == user_team_id
            elif user_role == UserRole.MEMBER:
                return bid.member_id == user_id
            
            return False
        except Exception as e:
            logger.error(f"Error checking bid access: {e}")
            return False

    def can_modify_bid(self, db: Session, bid_id: UUID, user_id: UUID, 
                      user_role: UserRole, user_team_id: Optional[UUID] = None) -> bool:
        """Check if user can modify specific bid."""
        try:
            if user_role == UserRole.ADMIN:
                return True
            
            bid = self.get_by_id(db, bid_id)
            if not bid:
                return False
            
            if user_role == UserRole.SUB_ADMIN:
                return bid.team_id == user_team_id
            elif user_role == UserRole.MEMBER:
                return bid.member_id == user_id and can_edit_bid(bid.created_at)
            
            return False
        except Exception as e:
            logger.error(f"Error checking bid modify permission: {e}")
            return False

    def update(self, db: Session, bid_id: UUID, bid_data: BidUpdate) -> Optional[Bid]:
        """Update bid."""
        try:
            bid = self.get_by_id(db, bid_id)
            if not bid:
                return None
            
            update_data = bid_data.dict(exclude_unset=True)
            
            # Recalculate costs if connects changed
            if 'connects_used' in update_data or 'boost_connects_used' in update_data:
                connects_used = update_data.get('connects_used', bid.connects_used)
                boost_connects = update_data.get('boost_connects_used', bid.boost_connects_used)
                
                connect_cost = calculate_connect_cost(connects_used, boost_connects)
                update_data['connect_cost'] = connect_cost
                update_data['total_cost'] = connect_cost
            
            return super().update(db, bid, **update_data)
        except Exception as e:
            logger.error(f"Error updating bid {bid_id}: {e}")
            return None

    def update_status(self, db: Session, bid_id: UUID, status: BidStatus) -> Optional[Bid]:
        """Update bid status."""
        try:
            bid = self.get_by_id(db, bid_id)
            if not bid:
                return None
            
            bid.status = status
            bid.last_status_change = datetime.utcnow()
            db.commit()
            db.refresh(bid)
            
            return bid
        except Exception as e:
            logger.error(f"Error updating bid status {bid_id}: {e}")
            db.rollback()
            return None

    def delete(self, db: Session, bid_id: UUID) -> bool:
        """Delete bid."""
        return super().delete(db, bid_id)

    def get_statistics(self, db: Session, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get bid statistics."""
        try:
            query = db.query(Bid)
            
            if filters:
                if filters.get('team_id'):
                    query = query.filter(Bid.team_id == filters['team_id'])
                if filters.get('member_id'):
                    query = query.filter(Bid.member_id == filters['member_id'])
                if filters.get('vertical_id'):
                    query = query.filter(Bid.vertical_id == filters['vertical_id'])
                if filters.get('date_from'):
                    query = query.filter(Bid.submitted_at >= filters['date_from'])
                if filters.get('date_to'):
                    query = query.filter(Bid.submitted_at <= filters['date_to'])
            
            total_bids = query.count()
            wins = query.filter(Bid.status == BidStatus.WON).count()
            total_connects = query.with_entities(func.sum(Bid.connects_used + Bid.boost_connects_used)).scalar() or 0
            total_cost = query.with_entities(func.sum(Bid.total_cost)).scalar() or Decimal('0')
            
            win_rate = Decimal(wins) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
            
            # Calculate average response time
            response_time_query = query.filter(
                and_(
                    Bid.status.in_([BidStatus.VIEWED, BidStatus.RESPONDED, BidStatus.WON]),
                    Bid.last_status_change > Bid.submitted_at
                )
            )
            
            avg_response_time = None
            if response_time_query.count() > 0:
                response_times = []
                for bid in response_time_query.all():
                    response_time = (bid.last_status_change - bid.submitted_at).total_seconds() / 3600
                    response_times.append(response_time)
                
                if response_times:
                    avg_response_time = sum(response_times) / len(response_times)
            
            return {
                'total_bids': total_bids,
                'wins': wins,
                'win_rate': win_rate,
                'total_connects_used': total_connects,
                'total_cost': total_cost,
                'avg_response_time_hours': Decimal(str(avg_response_time)) if avg_response_time else None
            }
        except Exception as e:
            logger.error(f"Error getting bid statistics: {e}")
            return {}

    def get_team_statistics(self, db: Session, team_id: Optional[UUID] = None,
                           user_role: UserRole = None, 
                           requesting_user_team_id: Optional[UUID] = None) -> List[TeamBidStats]:
        """Get team bid statistics."""
        try:
            query = db.query(
                Team.id.label('team_id'),
                Team.name.label('team_name'),
                func.count(Bid.id).label('total_bids'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects_used'),
                func.sum(Bid.total_cost).label('total_connect_cost'),
                func.sum(case((Bid.status == BidStatus.WON, 1), else_=0)).label('wins'),
                func.sum(case((Bid.status == BidStatus.WON, 
                              case((Bid.budget_type == 'fixed', (Bid.budget_min + Bid.budget_max) / 2),
                                   else_=Bid.hourly_rate * Bid.estimated_hours)), else_=0)).label('total_earnings'),
                func.count(func.distinct(User.id)).label('active_members')
            ).join(Team, Bid.team_id == Team.id).join(User, Bid.member_id == User.id)
            
            # Apply role-based filtering
            if user_role == UserRole.SUB_ADMIN and requesting_user_team_id:
                query = query.filter(Team.id == requesting_user_team_id)
            elif team_id:
                query = query.filter(Team.id == team_id)
            
            results = query.group_by(Team.id, Team.name).all()
            
            team_stats = []
            for result in results:
                win_rate = Decimal(result.wins) / Decimal(result.total_bids) * 100 if result.total_bids > 0 else Decimal('0')
                avg_bid_value = result.total_earnings / result.wins if result.wins > 0 else None
                
                team_stats.append(TeamBidStats(
                    team_id=result.team_id,
                    team_name=result.team_name,
                    total_bids=result.total_bids or 0,
                    total_connects_used=result.total_connects_used or 0,
                    total_connect_cost=result.total_connect_cost or Decimal('0'),
                    wins=result.wins or 0,
                    win_rate=win_rate,
                    total_earnings=result.total_earnings or Decimal('0'),
                    active_members=result.active_members or 0,
                    avg_bid_value=avg_bid_value
                ))
            
            return team_stats
        except Exception as e:
            logger.error(f"Error getting team statistics: {e}")
            return []

    def get_member_rankings(self, db: Session, filters: MemberRankingFilter,
                           user_role: UserRole, user_team_id: Optional[UUID] = None,
                           skip: int = 0, limit: int = 20) -> PaginatedResponse[MemberBidRanking]:
        """Get member bid rankings."""
        try:
            query = db.query(
                User.id.label('member_id'),
                func.concat(User.first_name, ' ', User.last_name).label('member_name'),
                User.email.label('email'),
                Team.id.label('team_id'),
                Team.name.label('team_name'),
                func.count(Bid.id).label('total_bids'),
                func.sum(case((Bid.status == BidStatus.WON, 1), else_=0)).label('wins'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects_used'),
                func.sum(Bid.total_cost).label('total_connect_cost'),
                func.sum(case((Bid.status == BidStatus.WON, 
                              case((Bid.budget_type == 'fixed', (Bid.budget_min + Bid.budget_max) / 2),
                                   else_=Bid.hourly_rate * Bid.estimated_hours)), else_=0)).label('total_earnings'),
                func.max(Bid.submitted_at).label('last_bid_date')
            ).join(Bid, User.id == Bid.member_id).join(Team, User.team_id == Team.id)
            
            # Apply role-based filtering
            if user_role == UserRole.SUB_ADMIN and user_team_id:
                query = query.filter(User.team_id == user_team_id)
            elif user_role == UserRole.MEMBER:
                # Members can only see their own ranking
                pass  # This would be handled in the service layer
            
            # Apply filters
            if filters.team_id:
                query = query.filter(User.team_id == filters.team_id)
            if filters.vertical_id:
                query = query.filter(Bid.vertical_id == filters.vertical_id)
            if filters.date_from:
                query = query.filter(Bid.submitted_at >= filters.date_from)
            if filters.date_to:
                query = query.filter(Bid.submitted_at <= filters.date_to)
            if filters.min_bids:
                query = query.having(func.count(Bid.id) >= filters.min_bids)
            
            query = query.group_by(User.id, User.first_name, User.last_name, User.email, Team.id, Team.name)
            
            # Apply sorting
            if filters.sort_field == BidSortField.WIN_RATE:
                if filters.sort_direction == SortDirection.DESC:
                    query = query.order_by(desc(func.sum(case((Bid.status == BidStatus.WON, 1), else_=0)) / func.count(Bid.id)))
                else:
                    query = query.order_by(asc(func.sum(case((Bid.status == BidStatus.WON, 1), else_=0)) / func.count(Bid.id)))
            elif filters.sort_field == BidSortField.TOTAL_BIDS:
                if filters.sort_direction == SortDirection.DESC:
                    query = query.order_by(desc(func.count(Bid.id)))
                else:
                    query = query.order_by(asc(func.count(Bid.id)))
            
            total_count = query.count()
            results = query.offset(skip).limit(limit).all()
            
            rankings = []
            for idx, result in enumerate(results):
                win_rate = Decimal(result.wins) / Decimal(result.total_bids) * 100 if result.total_bids > 0 else Decimal('0')
                avg_bid_value = result.total_earnings / result.wins if result.wins > 0 else None
                
                rankings.append(MemberBidRanking(
                    member_id=result.member_id,
                    member_name=result.member_name,
                    email=result.email,
                    team_id=result.team_id,
                    team_name=result.team_name,
                    total_bids=result.total_bids or 0,
                    wins=result.wins or 0,
                    win_rate=win_rate,
                    total_connects_used=result.total_connects_used or 0,
                    total_connect_cost=result.total_connect_cost or Decimal('0'),
                    total_earnings=result.total_earnings or Decimal('0'),
                    avg_bid_value=avg_bid_value,
                    last_bid_date=result.last_bid_date,
                    rank=skip + idx + 1
                ))
            
            return PaginatedResponse(
                items=rankings,
                next_cursor=f"offset:{skip + limit}" if len(rankings) == limit else None,
                count=total_count
            )
        except Exception as e:
            logger.error(f"Error getting member rankings: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_earnings(self, db: Session, team_id: Optional[UUID] = None,
                    member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                    date_from: Optional[datetime] = None, 
                    date_to: Optional[datetime] = None) -> EarningsResponse:
        """Get earnings data with breakdown."""
        try:
            query = db.query(Bid).filter(Bid.status == BidStatus.WON)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if member_id:
                query = query.filter(Bid.member_id == member_id)
            if vertical_id:
                query = query.filter(Bid.vertical_id == vertical_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            won_bids = query.all()
            won_bids_count = len(won_bids)
            
            total_earnings = sum(
                float(estimate_project_value(
                    bid.budget_type.value, bid.budget_min, bid.budget_max,
                    bid.hourly_rate, bid.estimated_hours
                ) or 0) for bid in won_bids
            )
            
            avg_earnings_per_bid = Decimal(total_earnings) / won_bids_count if won_bids_count > 0 else Decimal('0')
            
            # Get vertical breakdown
            vertical_breakdown = self._get_vertical_earnings_breakdown(db, query.filter())
            
            # Get team breakdown
            team_breakdown = self._get_team_earnings_breakdown(db, query.filter())
            
            # Get member breakdown
            member_breakdown = self._get_member_earnings_breakdown(db, query.filter())
            
            return EarningsResponse(
                total_earnings=Decimal(str(total_earnings)),
                won_bids_count=won_bids_count,
                avg_earnings_per_bid=avg_earnings_per_bid,
                period_start=date_from,
                period_end=date_to,
                breakdown_by_vertical=vertical_breakdown,
                breakdown_by_team=team_breakdown,
                breakdown_by_member=member_breakdown
            )
        except Exception as e:
            logger.error(f"Error getting earnings: {e}")
            return EarningsResponse(
                total_earnings=Decimal('0'),
                won_bids_count=0,
                avg_earnings_per_bid=Decimal('0')
            )

    def get_bid_analytics(self, db: Session, team_id: Optional[UUID] = None,
                         member_id: Optional[UUID] = None,
                         date_from: Optional[datetime] = None,
                         date_to: Optional[datetime] = None) -> BidAnalytics:
        """Get advanced bid analytics."""
        try:
            query = db.query(Bid)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if member_id:
                query = query.filter(Bid.member_id == member_id)
            if date_from:
                query = query.filter(Bid.submitted_at >= date_from)
            if date_to:
                query = query.filter(Bid.submitted_at <= date_to)
            
            total_bids = query.count()
            wins = query.filter(Bid.status == BidStatus.WON).count()
            conversion_rate = Decimal(wins) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
            
            # Calculate average time to response
            response_bids = query.filter(
                and_(
                    Bid.status.in_([BidStatus.VIEWED, BidStatus.RESPONDED, BidStatus.WON]),
                    Bid.last_status_change > Bid.submitted_at
                )
            ).all()
            
            avg_time_to_response = None
            if response_bids:
                response_times = [
                    (bid.last_status_change - bid.submitted_at).total_seconds() / 3600
                    for bid in response_bids
                ]
                avg_time_to_response = Decimal(str(sum(response_times) / len(response_times)))
            
            # Get top verticals
            top_verticals = self._get_top_verticals(db, query)
            
            # Get monthly trends
            monthly_trends = self.get_monthly_trends(db, team_id, member_id, 12)
            
            # Performance metrics
            performance_metrics = {
                'response_rate': (query.filter(Bid.status != BidStatus.NOT_VIEWED).count() / total_bids * 100) if total_bids > 0 else 0,
                'decline_rate': (query.filter(Bid.status == BidStatus.DECLINED).count() / total_bids * 100) if total_bids > 0 else 0,
                'avg_connects_per_bid': query.with_entities(func.avg(Bid.connects_used)).scalar() or 0,
                'avg_cost_per_bid': query.with_entities(func.avg(Bid.total_cost)).scalar() or 0
            }
            
            return BidAnalytics(
                conversion_rate=conversion_rate,
                avg_time_to_response=avg_time_to_response,
                top_verticals=top_verticals,
                monthly_trends=monthly_trends,
                performance_metrics=performance_metrics
            )
        except Exception as e:
            logger.error(f"Error getting bid analytics: {e}")
            return BidAnalytics(
                conversion_rate=Decimal('0'),
                top_verticals=[],
                monthly_trends=[],
                performance_metrics={}
            )

    def get_monthly_trends(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None,
                          months: int = 12) -> List[MonthlyTrend]:
        """Get monthly bid trends."""
        try:
            start_date = datetime.utcnow() - timedelta(days=months * 30)
            
            query = db.query(
                func.to_char(Bid.submitted_at, 'YYYY-MM').label('month'),
                func.count(Bid.id).label('total_bids'),
                func.sum(case((Bid.status == BidStatus.WON, 1), else_=0)).label('wins'),
                func.sum(case((Bid.status == BidStatus.WON, 
                              case((Bid.budget_type == 'fixed', (Bid.budget_min + Bid.budget_max) / 2),
                                   else_=Bid.hourly_rate * Bid.estimated_hours)), else_=0)).label('earnings'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('connects_used')
            ).filter(Bid.submitted_at >= start_date)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if member_id:
                query = query.filter(Bid.member_id == member_id)
            
            results = query.group_by(func.to_char(Bid.submitted_at, 'YYYY-MM')).order_by('month').all()
            
            trends = []
            for result in results:
                win_rate = Decimal(result.wins) / Decimal(result.total_bids) * 100 if result.total_bids > 0 else Decimal('0')
                
                trends.append(MonthlyTrend(
                    month=result.month,
                    total_bids=result.total_bids or 0,
                    wins=result.wins or 0,
                    win_rate=win_rate,
                    earnings=result.earnings or Decimal('0'),
                    connects_used=result.connects_used or 0
                ))
            
            return trends
        except Exception as e:
            logger.error(f"Error getting monthly trends: {e}")
            return []

    def bulk_update_status(self, db: Session, bid_ids: List[UUID], 
                          status: BidStatus, user_id: UUID, user_role: UserRole,
                          user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk update bid status with permission checks."""
        try:
            updated_bids = []
            errors = []
            
            for bid_id in bid_ids:
                if self.can_modify_bid(db, bid_id, user_id, user_role, user_team_id):
                    bid = self.update_status(db, bid_id, status)
                    if bid:
                        updated_bids.append(bid)
                    else:
                        errors.append(f"Failed to update bid {bid_id}")
                else:
                    errors.append(f"No permission to update bid {bid_id}")
            
            return BulkOperationResult(
                success_count=len(updated_bids),
                failed_count=len(errors),
                total_count=len(bid_ids),
                errors=errors,
                updated_bids=[]  # Would be converted to BidResponse in service layer
            )
        except Exception as e:
            logger.error(f"Error bulk updating bid status: {e}")
            return BulkOperationResult(
                success_count=0,
                failed_count=len(bid_ids),
                total_count=len(bid_ids),
                errors=[str(e)]
            )

    def bulk_delete(self, db: Session, bid_ids: List[UUID], 
                   user_id: UUID, user_role: UserRole,
                   user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk delete bids with permission checks."""
        try:
            deleted_count = 0
            errors = []
            
            for bid_id in bid_ids:
                if self.can_modify_bid(db, bid_id, user_id, user_role, user_team_id):
                    if self.delete(db, bid_id):
                        deleted_count += 1
                    else:
                        errors.append(f"Failed to delete bid {bid_id}")
                else:
                    errors.append(f"No permission to delete bid {bid_id}")
            
            return BulkOperationResult(
                success_count=deleted_count,
                failed_count=len(errors),
                total_count=len(bid_ids),
                errors=errors
            )
        except Exception as e:
            logger.error(f"Error bulk deleting bids: {e}")
            return BulkOperationResult(
                success_count=0,
                failed_count=len(bid_ids),
                total_count=len(bid_ids),
                errors=[str(e)]
            )

    def bulk_assign_team(self, db: Session, bid_ids: List[UUID], 
                        target_team_id: UUID, user_id: UUID, user_role: UserRole,
                        user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk assign bids to team with permission checks."""
        try:
            if user_role != UserRole.ADMIN:
                return BulkOperationResult(
                    success_count=0,
                    failed_count=len(bid_ids),
                    total_count=len(bid_ids),
                    errors=["Only admins can reassign bids to different teams"]
                )
            
            updated_count = 0
            errors = []
            
            for bid_id in bid_ids:
                bid = self.get_by_id(db, bid_id)
                if bid:
                    bid.team_id = target_team_id
                    db.commit()
                    updated_count += 1
                else:
                    errors.append(f"Bid {bid_id} not found")
            
            return BulkOperationResult(
                success_count=updated_count,
                failed_count=len(errors),
                total_count=len(bid_ids),
                errors=errors
            )
        except Exception as e:
            logger.error(f"Error bulk assigning team: {e}")
            db.rollback()
            return BulkOperationResult(
                success_count=0,
                failed_count=len(bid_ids),
                total_count=len(bid_ids),
                errors=[str(e)]
            )

    def get_recent_bids(self, db: Session, limit: int = 10, 
                       team_id: Optional[UUID] = None,
                       member_id: Optional[UUID] = None) -> List[Bid]:
        """Get recent bids."""
        try:
            query = db.query(Bid).options(
                joinedload(Bid.member),
                joinedload(Bid.vertical)
            )
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if member_id:
                query = query.filter(Bid.member_id == member_id)
            
            return query.order_by(desc(Bid.submitted_at)).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting recent bids: {e}")
            return []

    def get_winning_bids(self, db: Session, team_id: Optional[UUID] = None,
                        member_id: Optional[UUID] = None, skip: int = 0, 
                        limit: int = 20) -> PaginatedResponse:
        """Get winning bids."""
        filters = BidListFilter(status=BidStatus.WON)
        if team_id:
            filters.team_id = team_id
        if member_id:
            filters.member_id = member_id
        
        return self.get_all(db, filters, skip, limit)

    def get_pending_bids(self, db: Session, team_id: Optional[UUID] = None,
                        member_id: Optional[UUID] = None) -> List[Bid]:
        """Get pending bids (not viewed or viewed status)."""
        try:
            query = db.query(Bid).filter(
                Bid.status.in_([BidStatus.NOT_VIEWED, BidStatus.VIEWED])
            )
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if member_id:
                query = query.filter(Bid.member_id == member_id)
            
            return query.order_by(desc(Bid.submitted_at)).all()
        except Exception as e:
            logger.error(f"Error getting pending bids: {e}")
            return []

    def get_top_performers(self, db: Session, team_id: Optional[UUID] = None,
                          limit: int = 5) -> List[MemberBidRanking]:
        """Get top performing members."""
        try:
            filters = MemberRankingFilter(
                team_id=team_id,
                sort_field=BidSortField.WIN_RATE,
                sort_direction=SortDirection.DESC
            )
            
            result = self.get_member_rankings(
                db, filters, UserRole.ADMIN, None, 0, limit
            )
            
            return result.items
        except Exception as e:
            logger.error(f"Error getting top performers: {e}")
            return []

    def get_bids_for_receivables(self, db: Session) -> List[Bid]:
        """Get won bids that don't have receivables yet."""
        try:
            from models.models import Receivable
            
            return db.query(Bid).outerjoin(Receivable).filter(
                and_(
                    Bid.status == BidStatus.WON,
                    Receivable.bid_id.is_(None)
                )
            ).all()
        except Exception as e:
            logger.error(f"Error getting bids for receivables: {e}")
            return []

    def get_performance_trends(self, db: Session, team_id: Optional[UUID] = None,
                              member_id: Optional[UUID] = None, 
                              days: int = 30) -> List[Dict[str, Any]]:
        """Get performance trends over time."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            query = db.query(
                func.date(Bid.submitted_at).label('date'),
                func.count(Bid.id).label('total_bids'),
                func.count(func.nullif(Bid.status != BidStatus.WON, True)).label('wins')
            ).filter(Bid.submitted_at >= start_date)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            if member_id:
                query = query.filter(Bid.member_id == member_id)
            
            results = query.group_by(func.date(Bid.submitted_at)).all()
            
            return [
                {
                    'date': result.date.isoformat(),
                    'total_bids': result.total_bids,
                    'wins': result.wins,
                    'win_rate': (result.wins / result.total_bids * 100) if result.total_bids > 0 else 0
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"Error getting performance trends: {e}")
            return []

    def calculate_estimated_value(self, bid: Bid) -> Optional[float]:
        """Calculate estimated value for a bid."""
        return float(estimate_project_value(
            bid.budget_type.value,
            bid.budget_min,
            bid.budget_max,
            bid.hourly_rate,
            bid.estimated_hours
        ) or 0)

    def can_edit(self, db: Session, bid_id: UUID, user_id: UUID) -> bool:
        """Check if user can edit the bid."""
        try:
            bid = self.get_by_id(db, bid_id)
            if not bid:
                return False
            
            if str(bid.member_id) != str(user_id):
                return False
            
            return can_edit_bid(bid.created_at)
        except Exception as e:
            logger.error(f"Error checking edit permission for bid {bid_id}: {e}")
            return False


    def _get_vertical_earnings_breakdown(self, db: Session, base_query) -> List[VerticalEarnings]:
        """Get earnings breakdown by vertical."""
        try:
            query = base_query.join(Vertical, Bid.vertical_id == Vertical.id).add_columns(
                Vertical.id, Vertical.name,
                func.count(Bid.id).label('won_bids'),
                func.sum(case((Bid.budget_type == 'fixed', (Bid.budget_min + Bid.budget_max) / 2),
                             else_=Bid.hourly_rate * Bid.estimated_hours)).label('earnings')
            ).group_by(Vertical.id, Vertical.name)
            
            results = query.all()
            
            breakdown = []
            for result in results:
                # Get total bids for this vertical to calculate win rate
                total_bids = db.query(Bid).filter(Bid.vertical_id == result.id).count()
                win_rate = Decimal(result.won_bids) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
                
                breakdown.append(VerticalEarnings(
                    vertical_id=result.id,
                    vertical_name=result.name,
                    earnings=result.earnings or Decimal('0'),
                    won_bids=result.won_bids or 0,
                    total_bids=total_bids,
                    win_rate=win_rate
                ))
            
            return breakdown
        except Exception as e:
            logger.error(f"Error getting vertical earnings breakdown: {e}")
            return []

    def _get_team_earnings_breakdown(self, db: Session, base_query) -> List[TeamEarnings]:
        """Get earnings breakdown by team."""
        try:
            query = base_query.join(Team, Bid.team_id == Team.id).add_columns(
                Team.id, Team.name,
                func.count(Bid.id).label('won_bids'),
                func.sum(case((Bid.budget_type == 'fixed', (Bid.budget_min + Bid.budget_max) / 2),
                             else_=Bid.hourly_rate * Bid.estimated_hours)).label('earnings')
            ).group_by(Team.id, Team.name)
            
            results = query.all()
            
            breakdown = []
            for result in results:
                total_bids = db.query(Bid).filter(Bid.team_id == result.id).count()
                win_rate = Decimal(result.won_bids) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
                
                breakdown.append(TeamEarnings(
                    team_id=result.id,
                    team_name=result.name,
                    earnings=result.earnings or Decimal('0'),
                    won_bids=result.won_bids or 0,
                    total_bids=total_bids,
                    win_rate=win_rate
                ))
            
            return breakdown
        except Exception as e:
            logger.error(f"Error getting team earnings breakdown: {e}")
            return []

    def _get_member_earnings_breakdown(self, db: Session, base_query) -> List[MemberEarnings]:
        """Get earnings breakdown by member."""
        try:
            query = base_query.join(User, Bid.member_id == User.id).add_columns(
                User.id, func.concat(User.first_name, ' ', User.last_name),
                func.count(Bid.id).label('won_bids'),
                func.sum(case((Bid.budget_type == 'fixed', (Bid.budget_min + Bid.budget_max) / 2),
                             else_=Bid.hourly_rate * Bid.estimated_hours)).label('earnings')
            ).group_by(User.id, User.first_name, User.last_name)
            
            results = query.all()
            
            breakdown = []
            for result in results:
                total_bids = db.query(Bid).filter(Bid.member_id == result.id).count()
                win_rate = Decimal(result.won_bids) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
                
                breakdown.append(MemberEarnings(
                    member_id=result.id,
                    member_name=result[1],  # The concatenated name
                    earnings=result.earnings or Decimal('0'),
                    won_bids=result.won_bids or 0,
                    total_bids=total_bids,
                    win_rate=win_rate
                ))
            
            return breakdown
        except Exception as e:
            logger.error(f"Error getting member earnings breakdown: {e}")
            return []

    def _get_top_verticals(self, db: Session, base_query) -> List[VerticalEarnings]:
        """Get top performing verticals."""
        try:
            won_bids_query = base_query.filter(Bid.status == BidStatus.WON)
            breakdown = self._get_vertical_earnings_breakdown(db, won_bids_query)
            
            # Sort by earnings and return top 10
            return sorted(breakdown, key=lambda x: x.earnings, reverse=True)[:10]
        except Exception as e:
            logger.error(f"Error getting top verticals: {e}")
            return []