from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.vertical import (
    VerticalCreate, VerticalUpdate, VerticalResponse, VerticalListFilter,
    VerticalStats
)
from schemas.common import SuccessResponse, PaginatedResponse


class IVerticalService(ABC):
    
    @abstractmethod
    def create_vertical(self, db: Session, vertical_data: VerticalCreate, created_by_id: UUID) -> VerticalResponse:
        """Create a new vertical."""
        pass
    
    @abstractmethod
    def get_vertical(self, db: Session, vertical_id: UUID) -> Optional[VerticalResponse]:
        """Get vertical by ID."""
        pass
    
    @abstractmethod
    def get_verticals(self, db: Session, filters: VerticalListFilter, skip: int = 0,
                     limit: int = 20, sort_by: str = "sort_order") -> PaginatedResponse[VerticalResponse]:
        """Get all verticals with filters and pagination."""
        pass
    
    @abstractmethod
    def update_vertical(self, db: Session, vertical_id: UUID, vertical_data: VerticalUpdate) -> Optional[VerticalResponse]:
        """Update vertical."""
        pass
    
    @abstractmethod
    def delete_vertical(self, db: Session, vertical_id: UUID) -> SuccessResponse:
        """Delete vertical."""
        pass
    
    @abstractmethod
    def get_children(self, db: Session, parent_id: UUID) -> List[VerticalResponse]:
        """Get child verticals."""
        pass
    
    @abstractmethod
    def get_hierarchy(self, db: Session, vertical_id: UUID) -> List[VerticalResponse]:
        """Get full hierarchy path for a vertical."""
        pass
    
    @abstractmethod
    def get_by_parent(self, db: Session, parent_id: Optional[UUID] = None) -> List[VerticalResponse]:
        """Get verticals by parent (root level if parent_id is None)."""
        pass
    
    @abstractmethod
    def get_statistics(self, db: Session, vertical_id: UUID, user_id: UUID, 
                      user_role: str, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get vertical statistics with access control."""
        pass
    
    @abstractmethod
    def get_performance_trends(self, db: Session, vertical_id: UUID, days: int = 30) -> List[Dict[str, Any]]:
        """Get vertical performance trends."""
        pass
    
    @abstractmethod
    def get_top_performing(self, db: Session, limit: int = 10) -> List[VerticalResponse]:
        """Get top performing verticals by success rate."""
        pass
    
    @abstractmethod
    def get_most_active(self, db: Session, limit: int = 10) -> List[VerticalResponse]:
        """Get most active verticals by bid count."""
        pass
    
    @abstractmethod
    def search(self, db: Session, query: str, limit: int = 20) -> List[VerticalResponse]:
        """Search verticals by name, description, or slug."""
        pass
    
    @abstractmethod
    def get_available_for_assignment(self, db: Session, user_id: UUID) -> List[VerticalResponse]:
        """Get verticals available for assignment to a user."""
        pass
    
    @abstractmethod
    def update_statistics(self, db: Session, vertical_id: UUID) -> None:
        """Manually update vertical statistics."""
        pass
    
    @abstractmethod
    def update_sort_order(self, db: Session, vertical_id: UUID, new_order: int) -> bool:
        """Update vertical sort order."""
        pass
    
    @abstractmethod
    def get_summary_statistics(self, db: Session) -> VerticalStats:
        """Get summary statistics for all verticals."""
        pass
    
    @abstractmethod
    def bulk_activate(self, db: Session, vertical_ids: List[UUID]) -> int:
        """Bulk activate verticals."""
        pass
    
    @abstractmethod
    def bulk_deactivate(self, db: Session, vertical_ids: List[UUID]) -> int:
        """Bulk deactivate verticals."""
        pass