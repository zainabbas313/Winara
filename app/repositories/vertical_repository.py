from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc, text, case, cast, String
from datetime import datetime, timedelta
from models.models import Vertical, Bid, UserVertical, BidStatus
from schemas.vertical import VerticalCreate, VerticalUpdate, VerticalListFilter
from schemas.common import PaginatedResponse
from interface.Irepositories.vertical_repository import IVerticalRepository
import logging


logger = logging.getLogger(__name__)


class VerticalRepository(IVerticalRepository):
    
    def create(self, db: Session, vertical_data: VerticalCreate, created_by_id: UUID) -> Vertical:
        """Create a new vertical."""
        try:
            vertical = Vertical(
                name=vertical_data.name,
                slug=vertical_data.slug,
                description=vertical_data.description,
                parent_id=vertical_data.parent_id,
                level=vertical_data.level or 0,
                sort_order=vertical_data.sort_order or 0,
                is_active=vertical_data.is_active if vertical_data.is_active is not None else True,
                requires_approval=vertical_data.requires_approval or False,
                competition_level=vertical_data.competition_level or 1,
                created_by_id=created_by_id
            )
            
            db.add(vertical)
            db.commit()
            db.refresh(vertical)
            return vertical
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating vertical: {str(e)}")
            raise
    
    def get_by_id(self, db: Session, vertical_id: UUID) -> Optional[Vertical]:
        """Get vertical by ID."""
        return db.query(Vertical).filter(Vertical.id == vertical_id).first()
    
    def get_by_slug(self, db: Session, slug: str) -> Optional[Vertical]:
        """Get vertical by slug."""
        return db.query(Vertical).filter(Vertical.slug == slug).first()
    
    def get_all(self, db: Session, filters: VerticalListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "sort_order") -> PaginatedResponse:
        """Get all verticals with filters and pagination."""
        query = db.query(Vertical)
        
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
        
        # Get total count before applying pagination
        total = query.count()
        
        # Apply sorting
        if sort_by.startswith("-"):
            field = sort_by[1:]
            query = query.order_by(desc(getattr(Vertical, field, Vertical.sort_order)))
        else:
            query = query.order_by(asc(getattr(Vertical, sort_by, Vertical.sort_order)))
        
        # Apply pagination
        items = query.offset(skip).limit(limit).all()
        
        return PaginatedResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    
    def get_by_parent(self, db: Session, parent_id: Optional[UUID] = None) -> List[Vertical]:
        """Get verticals by parent (root level if parent_id is None)."""
        return (db.query(Vertical)
                .filter(Vertical.parent_id == parent_id)
                .filter(Vertical.is_active == True)
                .order_by(Vertical.sort_order)
                .all())
    
    def get_children(self, db: Session, parent_id: UUID) -> List[Vertical]:
        """Get child verticals."""
        return (db.query(Vertical)
                .filter(Vertical.parent_id == parent_id)
                .filter(Vertical.is_active == True)
                .order_by(Vertical.sort_order)
                .all())
    
    def get_hierarchy(self, db: Session, vertical_id: UUID) -> List[Vertical]:
        """Get full hierarchy path for a vertical using recursive CTE."""
        # Using recursive Common Table Expression (CTE) to get hierarchy
        hierarchy_cte = text("""
            WITH RECURSIVE vertical_hierarchy AS (
                -- Base case: start with the requested vertical
                SELECT id, name, slug, parent_id, level, 0 as path_level
                FROM verticals 
                WHERE id = :vertical_id
                
                UNION ALL
                
                -- Recursive case: get parent verticals
                SELECT v.id, v.name, v.slug, v.parent_id, v.level, vh.path_level + 1
                FROM verticals v
                INNER JOIN vertical_hierarchy vh ON v.id = vh.parent_id
            )
            SELECT DISTINCT id FROM vertical_hierarchy 
            ORDER BY path_level DESC
        """)
        
        result = db.execute(hierarchy_cte, {"vertical_id": str(vertical_id)})
        vertical_ids = [row[0] for row in result.fetchall()]
        
        if not vertical_ids:
            return []
        
        # Fetch the actual vertical objects in the correct order
        verticals = []
        for vid in vertical_ids:
            vertical = self.get_by_id(db, UUID(vid))
            if vertical:
                verticals.append(vertical)
        
        return verticals
    
    def update(self, db: Session, vertical_id: UUID, vertical_data: VerticalUpdate) -> Optional[Vertical]:
        """Update vertical."""
        try:
            vertical = self.get_by_id(db, vertical_id)
            if not vertical:
                return None
            
            update_data = vertical_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(vertical, field, value)
            
            db.commit()
            db.refresh(vertical)
            return vertical
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating vertical {vertical_id}: {str(e)}")
            raise
    
    def delete(self, db: Session, vertical_id: UUID) -> bool:
        """Delete vertical if it has no dependencies."""
        try:
            vertical = self.get_by_id(db, vertical_id)
            if not vertical:
                return False
            
            # Check for children
            children_count = db.query(func.count(Vertical.id)).filter(Vertical.parent_id == vertical_id).scalar()
            if children_count > 0:
                raise ValueError("Cannot delete vertical with child verticals")
            
            # Check for assignments
            assignments_count = db.query(func.count(UserVertical.id)).filter(
                UserVertical.vertical_id == vertical_id,
                UserVertical.is_active == True
            ).scalar()
            if assignments_count > 0:
                raise ValueError("Cannot delete vertical with active assignments")
            
            # Check for bids
            bids_count = db.query(func.count(Bid.id)).filter(Bid.vertical_id == vertical_id).scalar()
            if bids_count > 0:
                raise ValueError("Cannot delete vertical with existing bids")
            
            db.delete(vertical)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting vertical {vertical_id}: {str(e)}")
            raise
    
    def update_statistics(self, db: Session, vertical_id: UUID) -> None:
        """Update vertical statistics from bid data."""
        try:
            # Calculate statistics from bids
            bid_stats = (db.query(
                func.sum(Bid.total_cost).label('total_earn'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('connect_used'),
                func.count(Bid.id).label('total_bids'),
                func.avg(
                    case(
                        [(Bid.budget_type == 'fixed', Bid.budget_max)],
                        else_=(Bid.hourly_rate * Bid.estimated_hours)
                    )
                ).label('avg_project_value'),
                func.count(
                    case([(Bid.status == BidStatus.WON, 1)])
                ).label('won_bids')
            )
            .filter(Bid.vertical_id == vertical_id)
            .first())
            
            if bid_stats and bid_stats.total_bids > 0:
                success_rate = (bid_stats.won_bids or 0) / bid_stats.total_bids
                
                vertical = self.get_by_id(db, vertical_id)
                if vertical:
                    vertical.total_earn = bid_stats.total_earn or 0
                    vertical.connect_used = bid_stats.connect_used or 0
                    vertical.total_bids = bid_stats.total_bids or 0
                    vertical.avg_project_value = bid_stats.avg_project_value or 0
                    vertical.success_rate = success_rate
                    
                    db.commit()
                    
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating statistics for vertical {vertical_id}: {str(e)}")
            raise
    
    def get_statistics(self, db: Session, vertical_id: UUID) -> Dict[str, Any]:
        """Get comprehensive vertical statistics."""
        vertical = self.get_by_id(db, vertical_id)
        if not vertical:
            return {}
        
        # Get bid statistics by status
        bid_stats_by_status = (db.query(
            Bid.status,
            func.count(Bid.id).label('count'),
            func.sum(Bid.total_cost).label('total_cost'),
            func.sum(Bid.connects_used + Bid.boost_connects_used).label('connects')
        )
        .filter(Bid.vertical_id == vertical_id)
        .group_by(Bid.status)
        .all())
        
        # Get recent performance (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_stats = (db.query(
            func.count(Bid.id).label('recent_bids'),
            func.count(
                case([(Bid.status == BidStatus.WON, 1)])
            ).label('recent_wins')
        )
        .filter(
            Bid.vertical_id == vertical_id,
            Bid.submitted_at >= thirty_days_ago
        )
        .first())
        
        # Get assigned users count
        assigned_users = db.query(func.count(UserVertical.id)).filter(
            UserVertical.vertical_id == vertical_id,
            UserVertical.is_active == True
        ).scalar()
        
        return {
            "vertical_id": str(vertical_id),
            "name": vertical.name,
            "total_earn": float(vertical.total_earn or 0),
            "connect_used": vertical.connect_used or 0,
            "total_bids": vertical.total_bids or 0,
            "success_rate": float(vertical.success_rate or 0),
            "avg_project_value": float(vertical.avg_project_value or 0),
            "competition_level": vertical.competition_level,
            "assigned_users": assigned_users,
            "status_breakdown": {
                status.value: {
                    "count": count,
                    "total_cost": float(total_cost or 0),
                    "connects": connects or 0
                }
                for status, count, total_cost, connects in bid_stats_by_status
            },
            "recent_performance": {
                "bids_last_30_days": recent_stats.recent_bids or 0,
                "wins_last_30_days": recent_stats.recent_wins or 0,
                "recent_success_rate": (
                    recent_stats.recent_wins / recent_stats.recent_bids 
                    if recent_stats.recent_bids > 0 else 0
                )
            }
        }
    
    def get_top_performing(self, db: Session, limit: int = 10) -> List[Vertical]:
        """Get top performing verticals by success rate."""
        return (db.query(Vertical)
                .filter(
                    Vertical.is_active == True,
                    Vertical.total_bids > 0,
                    Vertical.success_rate.isnot(None)
                )
                .order_by(desc(Vertical.success_rate), desc(Vertical.total_earn))
                .limit(limit)
                .all())
    
    def get_most_active(self, db: Session, limit: int = 10) -> List[Vertical]:
        """Get most active verticals by bid count."""
        return (db.query(Vertical)
                .filter(Vertical.is_active == True)
                .order_by(desc(Vertical.total_bids), desc(Vertical.total_earn))
                .limit(limit)
                .all())
    
    def search(self, db: Session, query: str, limit: int = 20) -> List[Vertical]:
        """Search verticals by name, description, or slug."""
        search_term = f"%{query}%"
        return (db.query(Vertical)
                .filter(
                    and_(
                        Vertical.is_active == True,
                        or_(
                            Vertical.name.ilike(search_term),
                            Vertical.description.ilike(search_term),
                            Vertical.slug.ilike(search_term)
                        )
                    )
                )
                .order_by(Vertical.name)
                .limit(limit)
                .all())
    
    def get_available_for_assignment(self, db: Session, user_id: UUID) -> List[Vertical]:
        """Get verticals available for assignment to a user."""
        # Get verticals that are active and not already assigned to the user
        assigned_vertical_ids = (db.query(UserVertical.vertical_id)
                               .filter(
                                   UserVertical.user_id == user_id,
                                   UserVertical.is_active == True
                               )
                               .subquery())
        
        return (db.query(Vertical)
                .filter(
                    Vertical.is_active == True,
                    ~Vertical.id.in_(assigned_vertical_ids)
                )
                .order_by(Vertical.name)
                .all())
    
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
            db.rollback()
            logger.error(f"Error updating sort order for vertical {vertical_id}: {str(e)}")
            raise
    
    def get_performance_trends(self, db: Session, vertical_id: UUID, 
                              days: int = 30) -> List[Dict[str, Any]]:
        """Get vertical performance trends over specified period."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Group bids by date for trend analysis
        trends = (db.query(
            func.date(Bid.submitted_at).label('date'),
            func.count(Bid.id).label('bids_count'),
            func.sum(Bid.total_cost).label('total_earned'),
            func.sum(Bid.connects_used + Bid.boost_connects_used).label('connects_used'),
            func.count(
                case([(Bid.status == BidStatus.WON, 1)])
            ).label('wins')
        )
        .filter(
            Bid.vertical_id == vertical_id,
            Bid.submitted_at >= start_date,
            Bid.submitted_at <= end_date
        )
        .group_by(func.date(Bid.submitted_at))
        .order_by(func.date(Bid.submitted_at))
        .all())
        
        return [
            {
                "date": trend.date.isoformat(),
                "bids_count": trend.bids_count,
                "total_earned": float(trend.total_earned or 0),
                "connects_used": trend.connects_used,
                "wins": trend.wins,
                "success_rate": trend.wins / trend.bids_count if trend.bids_count > 0 else 0
            }
            for trend in trends
        ]