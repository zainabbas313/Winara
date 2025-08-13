from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Bid, BidStatus, User, Team, Vertical
from schemas.bid import BidCreate, BidUpdate, BidListFilter
from schemas.common import PaginatedResponse
from interface.Irepositories.bid_repository import IBidRepository
from utils.helpers import calculate_connect_cost, estimate_project_value, can_edit_bid
from core.config.config import settings
from utils.sort_values import _apply_sorting
import logging

logger = logging.getLogger(__name__)


class BidRepository(BaseRepository[Bid], IBidRepository):
    def __init__(self):
        super().__init__(Bid)

    def create(self, db: Session, bid_data: BidCreate) -> Bid:
        """Create a new bid."""
        try:
            # Calculate connect costs
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
            query = self._apply_bid_filters(query, filters)
            
            # Apply sorting
            query = _apply_sorting(query, sort_by, Bid)
            
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

    def get_by_member(self, db: Session, member_id: UUID, filters: BidListFilter,
                     skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get bids by member with filters."""
        filters.member_id = member_id
        return self.get_all(db, filters, skip, limit)

    def get_by_team(self, db: Session, team_id: UUID, filters: BidListFilter,
                   skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get bids by team with filters."""
        filters.team_id = team_id
        return self.get_all(db, filters, skip, limit)

    def get_by_vertical(self, db: Session, vertical_id: UUID, skip: int = 0, 
                       limit: int = 20) -> PaginatedResponse:
        """Get bids by vertical."""
        filters = BidListFilter(vertical_id=vertical_id)
        return self.get_all(db, filters, skip, limit)

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

    def can_edit(self, db: Session, bid_id: UUID, user_id: UUID) -> bool:
        """Check if user can edit the bid."""
        try:
            bid = self.get_by_id(db, bid_id)
            if not bid:
                return False
            
            # Only the bid creator can edit
            if str(bid.member_id) != str(user_id):
                return False
            
            # Check edit window
            return can_edit_bid(bid.created_at)
        except Exception as e:
            logger.error(f"Error checking edit permission for bid {bid_id}: {e}")
            return False

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

    def get_team_statistics(self, db: Session, team_id: UUID, 
                           filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get team bid statistics."""
        if not filters:
            filters = {}
        filters['team_id'] = team_id
        return self.get_statistics(db, filters)

    def get_member_statistics(self, db: Session, member_id: UUID,
                             filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get member bid statistics."""
        if not filters:
            filters = {}
        filters['member_id'] = member_id
        return self.get_statistics(db, filters)

    def get_vertical_statistics(self, db: Session, vertical_id: UUID,
                               filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get vertical bid statistics."""
        if not filters:
            filters = {}
        filters['vertical_id'] = vertical_id
        return self.get_statistics(db, filters)

    def get_recent_bids(self, db: Session, limit: int = 10, team_id: Optional[UUID] = None,
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

    def bulk_update_status(self, db: Session, bid_ids: List[UUID], 
                          status: BidStatus) -> List[Bid]:
        """Bulk update bid status."""
        try:
            updated_bids = []
            for bid_id in bid_ids:
                bid = self.update_status(db, bid_id, status)
                if bid:
                    updated_bids.append(bid)
            
            return updated_bids
        except Exception as e:
            logger.error(f"Error bulk updating bid status: {e}")
            return []

    def get_bids_for_receivables(self, db: Session) -> List[Bid]:
        """Get won bids that don't have receivables yet."""
        try:
            from models import Receivable
            
            return db.query(Bid).outerjoin(Receivable).filter(
                and_(
                    Bid.status == BidStatus.WON,
                    Receivable.bid_id.is_(None)
                )
            ).all()
        except Exception as e:
            logger.error(f"Error getting bids for receivables: {e}")
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

    def _apply_bid_filters(self, query, filters: BidListFilter):
        """Apply bid-specific filters to query."""
        if filters.status:
            query = query.filter(Bid.status == filters.status)
        
        if filters.team_id:
            query = query.filter(Bid.team_id == filters.team_id)
        
        if filters.member_id:
            query = query.filter(Bid.member_id == filters.member_id)
        
        if filters.vertical_id:
            query = query.filter(Bid.vertical_id == filters.vertical_id)
        
        if filters.budget_type:
            query = query.filter(Bid.budget_type == filters.budget_type)
        
        if filters.date_from:
            query = query.filter(Bid.submitted_at >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Bid.submitted_at <= filters.date_to)
        
        if filters.q:
            search_term = f"%{filters.q}%"
            query = query.filter(
                or_(
                    Bid.job_title.ilike(search_term),
                    Bid.client_name.ilike(search_term),
                    Bid.proposal_text.ilike(search_term)
                )
            )
        
        return query