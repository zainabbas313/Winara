from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Vertical, UserVertical, Bid, BidStatus
from schemas.vertical import VerticalCreate, VerticalUpdate, VerticalListFilter
from schemas.common import PaginatedResponse
from interface.Irepositories.vertical_repository import IVerticalRepository
import logging

logger = logging.getLogger(__name__)


class VerticalRepository(BaseRepository[Vertical], IVerticalRepository):
    def __init__(self):
        super().__init__(Vertical)

    def create(self, db: Session, vertical_data: VerticalCreate, created_by_id: UUID) -> Vertical:
        """Create a new vertical."""
        try:
            vertical_dict = vertical_data.dict()
            vertical_dict['created_by_id'] = created_by_id
            return super().create(db, **vertical_dict)
        except Exception as e:
            logger.error(f"Error creating vertical: {e}")
            raise

    def get_by_id(self, db: Session, vertical_id: UUID) -> Optional[Vertical]:
        """Get vertical by ID with related data."""
        try:
            return db.query(Vertical).options(
                joinedload(Vertical.parent),
                joinedload(Vertical.children),
                joinedload(Vertical.created_by)
            ).filter(Vertical.id == vertical_id).first()
        except Exception as e:
            logger.error(f"Error getting vertical {vertical_id}: {e}")
            return None

    def get_by_slug(self, db: Session, slug: str) -> Optional[Vertical]:
        """Get vertical by slug."""
        try:
            return db.query(Vertical).filter(Vertical.slug == slug).first()
        except Exception as e:
            logger.error(f"Error getting vertical by slug {slug}: {e}")
            return None

    def get_all(self, db: Session, filters: VerticalListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "sort_order") -> PaginatedResponse:
        """Get all verticals with filters and pagination."""
        try:
            query = db.query(Vertical).options(
                joinedload(Vertical.parent),
                joinedload(Vertical.created_by)
            )
            
            # Apply filters
            if filters.parent_id is not None:
                query = query.filter(Vertical.parent_id == filters.parent_id)
            
            if filters.is_active is not None:
                query = query.filter(Vertical.is_active == filters.is_active)
            
            if filters.q:
                search_term = f"%{filters.q}%"
                query = query.filter(
                    or_(
                        Vertical.name.ilike(search_term),
                        Vertical.description.ilike(search_term),
                        Vertical.slug.ilike(search_term)
                    )
                )
            
            # Apply sorting
            query = self._apply_sorting(query, sort_by)
            
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
            logger.error(f"Error getting verticals: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_by_parent(self, db: Session, parent_id: Optional[UUID] = None) -> List[Vertical]:
        """Get verticals by parent (root level if parent_id is None)."""
        try:
            query = db.query(Vertical).filter(Vertical.parent_id == parent_id)
            return query.order_by(Vertical.sort_order, Vertical.name).all()
        except Exception as e:
            logger.error(f"Error getting verticals by parent {parent_id}: {e}")
            return []

    def get_children(self, db: Session, parent_id: UUID) -> List[Vertical]:
        """Get child verticals."""
        try:
            return db.query(Vertical).filter(
                and_(
                    Vertical.parent_id == parent_id,
                    Vertical.is_active == True
                )
            ).order_by(Vertical.sort_order, Vertical.name).all()
        except Exception as e:
            logger.error(f"Error getting children for vertical {parent_id}: {e}")
            return []

    def get_hierarchy(self, db: Session, vertical_id: UUID) -> List[Vertical]:
        """Get full hierarchy path for a vertical."""
        try:
            hierarchy = []
            current = self.get_by_id(db, vertical_id)
            
            while current:
                hierarchy.insert(0, current)  # Insert at beginning to maintain order
                if current.parent_id:
                    current = self.get_by_id(db, current.parent_id)
                else:
                    break
            
            return hierarchy
        except Exception as e:
            logger.error(f"Error getting hierarchy for vertical {vertical_id}: {e}")
            return []

    def update(self, db: Session, vertical_id: UUID, vertical_data: VerticalUpdate) -> Optional[Vertical]:
        """Update vertical."""
        try:
            vertical = self.get_by_id(db, vertical_id)
            if not vertical:
                return None
            
            update_data = vertical_data.dict(exclude_unset=True)
            return super().update(db, vertical, **update_data)
        except Exception as e:
            logger.error(f"Error updating vertical {vertical_id}: {e}")
            return None

    def delete(self, db: Session, vertical_id: UUID) -> bool:
        """Delete vertical."""
        try:
            # Check if vertical has children
            children_count = db.query(Vertical).filter(Vertical.parent_id == vertical_id).count()
            if children_count > 0:
                logger.warning(f"Cannot delete vertical {vertical_id}: has {children_count} children")
                return False
            
            # Check if vertical is assigned to users
            assignments_count = db.query(UserVertical).filter(
                and_(
                    UserVertical.vertical_id == vertical_id,
                    UserVertical.is_active == True
                )
            ).count()
            if assignments_count > 0:
                logger.warning(f"Cannot delete vertical {vertical_id}: assigned to {assignments_count} users")
                return False
            
            # Check if vertical has bids
            bids_count = db.query(Bid).filter(Bid.vertical_id == vertical_id).count()
            if bids_count > 0:
                logger.warning(f"Cannot delete vertical {vertical_id}: has {bids_count} bids")
                return False
            
            return super().delete(db, vertical_id)
        except Exception as e:
            logger.error(f"Error deleting vertical {vertical_id}: {e}")
            return False

    def update_statistics(self, db: Session, vertical_id: UUID) -> None:
        """Update vertical statistics (total_earn, connect_used, total_bids, success_rate)."""
        try:
            vertical = self.get_by_id(db, vertical_id)
            if not vertical:
                return
            
            # Calculate statistics from bids
            bid_stats = db.query(
                func.count(Bid.id).label('total_bids'),
                func.count(func.nullif(Bid.status != BidStatus.WON, True)).label('wins'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects'),
                func.sum(Bid.total_cost).label('total_cost')
            ).filter(Bid.vertical_id == vertical_id).first()
            
            # Calculate total earnings from won bids
            won_bids = db.query(Bid).filter(
                and_(
                    Bid.vertical_id == vertical_id,
                    Bid.status == BidStatus.WON
                )
            ).all()
            
            total_earn = Decimal('0')
            project_values = []
            
            for bid in won_bids:
                if bid.budget_type.value == 'fixed' and bid.budget_min:
                    value = bid.budget_min
                    total_earn += value
                    project_values.append(value)
                elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                    value = bid.hourly_rate * bid.estimated_hours
                    total_earn += value
                    project_values.append(value)
            
            # Calculate average project value
            avg_project_value = None
            if project_values:
                avg_project_value = sum(project_values) / len(project_values)
            
            # Calculate success rate
            total_bids = bid_stats.total_bids or 0
            wins = bid_stats.wins or 0
            success_rate = None
            if total_bids > 0:
                success_rate = Decimal(wins) / Decimal(total_bids)
            
            # Update vertical statistics
            vertical.total_bids = total_bids
            vertical.connect_used = bid_stats.total_connects or 0
            vertical.total_earn = total_earn
            vertical.avg_project_value = avg_project_value
            vertical.success_rate = success_rate
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating vertical statistics for {vertical_id}: {e}")
            db.rollback()

    def get_statistics(self, db: Session, vertical_id: UUID) -> Dict[str, Any]:
        """Get vertical statistics."""
        try:
            vertical = self.get_by_id(db, vertical_id)
            if not vertical:
                return {}
            
            # Get bid statistics
            bid_stats = db.query(
                func.count(Bid.id).label('total_bids'),
                func.count(func.nullif(Bid.status != BidStatus.WON, True)).label('wins'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects'),
                func.sum(Bid.total_cost).label('total_cost'),
                func.avg(Bid.competition_level).label('avg_competition')
            ).filter(Bid.vertical_id == vertical_id).first()
            
            # Get user assignment count
            assignment_count = db.query(UserVertical).filter(
                and_(
                    UserVertical.vertical_id == vertical_id,
                    UserVertical.is_active == True
                )
            ).count()
            
            # Calculate win rate
            total_bids = bid_stats.total_bids or 0
            wins = bid_stats.wins or 0
            win_rate = Decimal(wins) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
            
            return {
                'vertical_id': vertical_id,
                'vertical_name': vertical.name,
                'total_bids': total_bids,
                'wins': wins,
                'win_rate': win_rate,
                'total_connects_used': bid_stats.total_connects or 0,
                'total_cost': bid_stats.total_cost or Decimal('0'),
                'total_earn': vertical.total_earn or Decimal('0'),
                'avg_project_value': vertical.avg_project_value or Decimal('0'),
                'avg_competition_level': bid_stats.avg_competition or 0,
                'assigned_users': assignment_count,
                'competition_level': vertical.competition_level
            }
            
        except Exception as e:
            logger.error(f"Error getting vertical statistics for {vertical_id}: {e}")
            return {}

    def get_top_performing(self, db: Session, limit: int = 10) -> List[Vertical]:
        """Get top performing verticals by success rate."""
        try:
            return db.query(Vertical).filter(
                and_(
                    Vertical.is_active == True,
                    Vertical.success_rate.isnot(None),
                    Vertical.total_bids >= 5  # Minimum bids for meaningful statistics
                )
            ).order_by(desc(Vertical.success_rate)).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting top performing verticals: {e}")
            return []

    def get_most_active(self, db: Session, limit: int = 10) -> List[Vertical]:
        """Get most active verticals by bid count."""
        try:
            return db.query(Vertical).filter(
                Vertical.is_active == True
            ).order_by(desc(Vertical.total_bids)).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting most active verticals: {e}")
            return []

    def search(self, db: Session, query: str, limit: int = 20) -> List[Vertical]:
        """Search verticals by name or description."""
        try:
            search_term = f"%{query}%"
            return db.query(Vertical).filter(
                and_(
                    Vertical.is_active == True,
                    or_(
                        Vertical.name.ilike(search_term),
                        Vertical.description.ilike(search_term),
                        Vertical.slug.ilike(search_term)
                    )
                )
            ).order_by(Vertical.name).limit(limit).all()
        except Exception as e:
            logger.error(f"Error searching verticals: {e}")
            return []

    def get_available_for_assignment(self, db: Session, user_id: UUID) -> List[Vertical]:
        """Get verticals available for assignment to a user."""
        try:
            # Get verticals not already assigned to the user
            assigned_vertical_ids = db.query(UserVertical.vertical_id).filter(
                and_(
                    UserVertical.user_id == user_id,
                    UserVertical.is_active == True
                )
            ).subquery()
            
            return db.query(Vertical).filter(
                and_(
                    Vertical.is_active == True,
                    ~Vertical.id.in_(assigned_vertical_ids)
                )
            ).order_by(Vertical.level, Vertical.sort_order, Vertical.name).all()
        except Exception as e:
            logger.error(f"Error getting available verticals for user {user_id}: {e}")
            return []

    def update_sort_order(self, db: Session, vertical_id: UUID, new_order: int) -> bool:
        """Update vertical sort order."""
        try:
            vertical = self.get_by_id(db, vertical_id)
            if not vertical:
                return False
            
            vertical.sort_order = new_order
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating sort order for vertical {vertical_id}: {e}")
            db.rollback()
            return False

    def get_performance_trends(self, db: Session, vertical_id: UUID, 
                              days: int = 30) -> List[Dict[str, Any]]:
        """Get vertical performance trends."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get daily performance data
            performance_data = db.query(
                func.date(Bid.submitted_at).label('date'),
                func.count(Bid.id).label('daily_bids'),
                func.count(func.nullif(Bid.status != BidStatus.WON, True)).label('daily_wins'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('daily_connects')
            ).filter(
                and_(
                    Bid.vertical_id == vertical_id,
                    Bid.submitted_at >= start_date
                )
            ).group_by(func.date(Bid.submitted_at)).all()
            
            return [
                {
                    'date': p.date.isoformat(),
                    'bids': p.daily_bids,
                    'wins': p.daily_wins,
                    'connects_used': p.daily_connects or 0,
                    'win_rate': (p.daily_wins / p.daily_bids * 100) if p.daily_bids > 0 else 0
                }
                for p in performance_data
            ]
            
        except Exception as e:
            logger.error(f"Error getting performance trends for vertical {vertical_id}: {e}")
            return []