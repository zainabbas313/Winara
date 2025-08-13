from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from models.models import Vertical, UserVertical, UserRole
from schemas.vertical import (
    VerticalCreate, VerticalUpdate, VerticalResponse, VerticalListFilter,
    VerticalStats
)
from schemas.common import SuccessResponse, PaginatedResponse
from repositories.vertical_repository import VerticalRepository
from interface.Iservices.vertical_service import IVerticalService
import logging

logger = logging.getLogger(__name__)


class VerticalService(IVerticalService):
    
    def __init__(self):
        self.repository = VerticalRepository()
    
    def create_vertical(self, db: Session, vertical_data: VerticalCreate, created_by_id: UUID) -> VerticalResponse:
        """Create a new vertical."""
        try:
            # Check if slug is unique
            existing_vertical = self.repository.get_by_slug(db, vertical_data.slug)
            if existing_vertical:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vertical with this slug already exists"
                )
            
            # If parent_id is provided, validate parent exists and is active
            if vertical_data.parent_id:
                parent = self.repository.get_by_id(db, vertical_data.parent_id)
                if not parent:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Parent vertical not found"
                    )
                if not parent.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Parent vertical is not active"
                    )
                # Set level based on parent
                vertical_data.level = parent.level + 1
            
            vertical = self.repository.create(db, vertical_data, created_by_id)
            return self._to_response(vertical)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating vertical: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while creating vertical"
            )
    
    def get_vertical(self, db: Session, vertical_id: UUID) -> Optional[VerticalResponse]:
        """Get vertical by ID."""
        vertical = self.repository.get_by_id(db, vertical_id)
        return self._to_response(vertical) if vertical else None
    
    def get_verticals(self, db: Session, filters: VerticalListFilter, skip: int = 0,
                     limit: int = 20, sort_by: str = "sort_order") -> PaginatedResponse[VerticalResponse]:
        """Get all verticals with filters and pagination."""
        result = self.repository.get_all(db, filters, skip, limit, sort_by)
        
        return PaginatedResponse(
            items=[self._to_response(item) for item in result.items],
            total=result.total,
            skip=result.skip,
            limit=result.limit,
            has_next=result.has_next,
            has_prev=result.has_prev
        )
    
    def update_vertical(self, db: Session, vertical_id: UUID, vertical_data: VerticalUpdate) -> Optional[VerticalResponse]:
        """Update vertical."""
        try:
            # If slug is being updated, check uniqueness
            if vertical_data.slug:
                existing_vertical = self.repository.get_by_slug(db, vertical_data.slug)
                if existing_vertical and existing_vertical.id != vertical_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Vertical with this slug already exists"
                    )
            
            # If parent_id is being updated, validate parent
            if vertical_data.parent_id:
                # Prevent circular references
                if vertical_data.parent_id == vertical_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Vertical cannot be its own parent"
                    )
                
                parent = self.repository.get_by_id(db, vertical_data.parent_id)
                if not parent:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Parent vertical not found"
                    )
                
                # Check if setting this parent would create a circular reference
                hierarchy = self.repository.get_hierarchy(db, vertical_id)
                if any(v.id == vertical_data.parent_id for v in hierarchy):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This would create a circular reference"
                    )
            
            vertical = self.repository.update(db, vertical_id, vertical_data)
            return self._to_response(vertical) if vertical else None
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating vertical {vertical_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating vertical"
            )
    
    def delete_vertical(self, db: Session, vertical_id: UUID) -> SuccessResponse:
        """Delete vertical."""
        try:
            success = self.repository.delete(db, vertical_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vertical not found"
                )
            
            return SuccessResponse(message="Vertical deleted successfully")
            
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error deleting vertical {vertical_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while deleting vertical"
            )
    
    def get_children(self, db: Session, parent_id: UUID) -> List[VerticalResponse]:
        """Get child verticals."""
        children = self.repository.get_children(db, parent_id)
        return [self._to_response(child) for child in children]
    
    def get_hierarchy(self, db: Session, vertical_id: UUID) -> List[VerticalResponse]:
        """Get full hierarchy path for a vertical."""
        hierarchy = self.repository.get_hierarchy(db, vertical_id)
        return [self._to_response(vertical) for vertical in hierarchy]
    
    def get_by_parent(self, db: Session, parent_id: Optional[UUID] = None) -> List[VerticalResponse]:
        """Get verticals by parent (root level if parent_id is None)."""
        verticals = self.repository.get_by_parent(db, parent_id)
        return [self._to_response(vertical) for vertical in verticals]
    
    def get_statistics(self, db: Session, vertical_id: UUID, user_id: UUID, 
                      user_role: str, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get vertical statistics with access control."""
        # Access control logic
        if user_role == UserRole.ADMIN.value:
            # Admin can see statistics for any vertical
            pass
        elif user_role == UserRole.SUB_ADMIN.value:
            # Sub-admin can see statistics for verticals assigned to their team members
            if team_id:
                # Check if any team member has this vertical assigned
                has_access = db.query(UserVertical).join(
                    db.query(UserVertical.user_id).filter(
                        db.query(UserVertical).filter(
                            UserVertical.user_id.in_(
                                db.query(func.distinct(UserVertical.user_id)).filter(
                                    UserVertical.vertical_id == vertical_id,
                                    UserVertical.is_active == True
                                )
                            )
                        ).exists()
                    )
                ).first()
                
                if not has_access:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this vertical's statistics"
                    )
        else:  # MEMBER role
            # Member can only see statistics for their assigned verticals
            assignment = db.query(UserVertical).filter(
                UserVertical.user_id == user_id,
                UserVertical.vertical_id == vertical_id,
                UserVertical.is_active == True
            ).first()
            
            if not assignment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this vertical's statistics"
                )
        
        return self.repository.get_statistics(db, vertical_id)
    
    def get_performance_trends(self, db: Session, vertical_id: UUID, days: int = 30) -> List[Dict[str, Any]]:
        """Get vertical performance trends."""
        return self.repository.get_performance_trends(db, vertical_id, days)
    
    def get_top_performing(self, db: Session, limit: int = 10) -> List[VerticalResponse]:
        """Get top performing verticals by success rate."""
        verticals = self.repository.get_top_performing(db, limit)
        return [self._to_response(vertical) for vertical in verticals]
    
    def get_most_active(self, db: Session, limit: int = 10) -> List[VerticalResponse]:
        """Get most active verticals by bid count."""
        verticals = self.repository.get_most_active(db, limit)
        return [self._to_response(vertical) for vertical in verticals]
    
    def search(self, db: Session, query: str, limit: int = 20) -> List[VerticalResponse]:
        """Search verticals by name, description, or slug."""
        verticals = self.repository.search(db, query, limit)
        return [self._to_response(vertical) for vertical in verticals]
    
    def get_available_for_assignment(self, db: Session, user_id: UUID) -> List[VerticalResponse]:
        """Get verticals available for assignment to a user."""
        verticals = self.repository.get_available_for_assignment(db, user_id)
        return [self._to_response(vertical) for vertical in verticals]
    
    def update_statistics(self, db: Session, vertical_id: UUID) -> None:
        """Manually update vertical statistics."""
        try:
            # Verify vertical exists
            vertical = self.repository.get_by_id(db, vertical_id)
            if not vertical:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vertical not found"
                )
            
            self.repository.update_statistics(db, vertical_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating statistics for vertical {vertical_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating statistics"
            )
    
    def update_sort_order(self, db: Session, vertical_id: UUID, new_order: int) -> bool:
        """Update vertical sort order."""
        try:
            return self.repository.update_sort_order(db, vertical_id, new_order)
        except Exception as e:
            logger.error(f"Error updating sort order for vertical {vertical_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating sort order"
            )
    
    def get_summary_statistics(self, db: Session) -> VerticalStats:
        """Get summary statistics for all verticals."""
        try:
            # Get overall statistics
            total_verticals = db.query(func.count(Vertical.id)).scalar()
            active_verticals = db.query(func.count(Vertical.id)).filter(Vertical.is_active == True).scalar()
            
            # Get aggregated financial data
            financial_stats = db.query(
                func.sum(Vertical.total_earn).label('total_earnings'),
                func.sum(Vertical.connect_used).label('total_connects'),
                func.sum(Vertical.total_bids).label('total_bids'),
                func.avg(Vertical.success_rate).label('avg_success_rate'),
                func.avg(Vertical.avg_project_value).label('avg_project_value'),
                func.avg(Vertical.competition_level).label('avg_competition_level')
            ).filter(Vertical.is_active == True).first()
            
            # Get vertical distribution by level
            level_distribution = db.query(
                Vertical.level,
                func.count(Vertical.id).label('count')
            ).filter(Vertical.is_active == True).group_by(Vertical.level).all()
            
            return VerticalStats(
                total_verticals=total_verticals or 0,
                active_verticals=active_verticals or 0,
                inactive_verticals=(total_verticals or 0) - (active_verticals or 0),
                total_earnings=float(financial_stats.total_earnings or 0),
                total_connects_used=financial_stats.total_connects or 0,
                total_bids=financial_stats.total_bids or 0,
                average_success_rate=float(financial_stats.avg_success_rate or 0),
                average_project_value=float(financial_stats.avg_project_value or 0),
                average_competition_level=float(financial_stats.avg_competition_level or 0),
                level_distribution={
                    level: count for level, count in level_distribution
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting summary statistics: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while getting summary statistics"
            )
    
    def bulk_activate(self, db: Session, vertical_ids: List[UUID]) -> int:
        """Bulk activate verticals."""
        try:
            count = db.query(Vertical).filter(
                Vertical.id.in_(vertical_ids)
            ).update(
                {"is_active": True},
                synchronize_session=False
            )
            db.commit()
            return count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error bulk activating verticals: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while bulk activating verticals"
            )
    
    def bulk_deactivate(self, db: Session, vertical_ids: List[UUID]) -> int:
        """Bulk deactivate verticals."""
        try:
            count = db.query(Vertical).filter(
                Vertical.id.in_(vertical_ids)
            ).update(
                {"is_active": False},
                synchronize_session=False
            )
            db.commit()
            return count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error bulk deactivating verticals: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while bulk deactivating verticals"
            )
    
    def _to_response(self, vertical: Vertical) -> VerticalResponse:
        """Convert Vertical model to VerticalResponse schema."""
        return VerticalResponse(
            id=vertical.id,
            name=vertical.name,
            slug=vertical.slug,
            description=vertical.description,
            parent_id=vertical.parent_id,
            level=vertical.level,
            sort_order=vertical.sort_order,
            is_active=vertical.is_active,
            requires_approval=vertical.requires_approval,
            total_earn=vertical.total_earn,
            connect_used=vertical.connect_used,
            total_bids=vertical.total_bids,
            avg_project_value=vertical.avg_project_value,
            competition_level=vertical.competition_level,
            success_rate=vertical.success_rate,
            created_at=vertical.created_at,
            updated_at=vertical.updated_at,
            created_by_id=vertical.created_by_id
        )