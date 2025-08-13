from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.models import Vertical
from schemas.vertical import VerticalCreate, VerticalUpdate, VerticalListFilter
from schemas.common import PaginatedResponse


class IVerticalRepository(ABC):
    
    @abstractmethod
    def create(self, db: Session, vertical_data: VerticalCreate, created_by_id: UUID) -> Vertical:
        """Create a new vertical."""
        pass
    
    @abstractmethod
    def get_by_id(self, db: Session, vertical_id: UUID) -> Optional[Vertical]:
        """Get vertical by ID."""
        pass
    
    @abstractmethod
    def get_by_slug(self, db: Session, slug: str) -> Optional[Vertical]:
        """Get vertical by slug."""
        pass
    
    @abstractmethod
    def get_all(self, db: Session, filters: VerticalListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "sort_order") -> PaginatedResponse:
        """Get all verticals with filters and pagination."""
        pass
    
    @abstractmethod
    def get_by_parent(self, db: Session, parent_id: Optional[UUID] = None) -> List[Vertical]:
        """Get verticals by parent (root level if parent_id is None)."""
        pass
    
    @abstractmethod
    def get_children(self, db: Session, parent_id: UUID) -> List[Vertical]:
        """Get child verticals."""
        pass
    
    @abstractmethod
    def get_hierarchy(self, db: Session, vertical_id: UUID) -> List[Vertical]:
        """Get full hierarchy path for a vertical."""
        pass
    
    @abstractmethod
    def update(self, db: Session, vertical_id: UUID, vertical_data: VerticalUpdate) -> Optional[Vertical]:
        """Update vertical."""
        pass
    
    @abstractmethod
    def delete(self, db: Session, vertical_id: UUID) -> bool:
        """Delete vertical."""
        pass
    
    @abstractmethod
    def update_statistics(self, db: Session, vertical_id: UUID) -> None:
        """Update vertical statistics (total_earn, connect_used, total_bids, success_rate)."""
        pass
    
    @abstractmethod
    def get_statistics(self, db: Session, vertical_id: UUID) -> Dict[str, Any]:
        """Get vertical statistics."""
        pass
    
    @abstractmethod
    def get_top_performing(self, db: Session, limit: int = 10) -> List[Vertical]:
        """Get top performing verticals by success rate."""
        pass
    
    @abstractmethod
    def get_most_active(self, db: Session, limit: int = 10) -> List[Vertical]:
        """Get most active verticals by bid count."""
        pass
    
    @abstractmethod
    def search(self, db: Session, query: str, limit: int = 20) -> List[Vertical]:
        """Search verticals by name or description."""
        pass
    
    @abstractmethod
    def get_available_for_assignment(self, db: Session, user_id: UUID) -> List[Vertical]:
        """Get verticals available for assignment to a user."""
        pass
    
    @abstractmethod
    def update_sort_order(self, db: Session, vertical_id: UUID, new_order: int) -> bool:
        """Update vertical sort order."""
        pass
    
    @abstractmethod
    def get_performance_trends(self, db: Session, vertical_id: UUID, 
                              days: int = 30) -> List[Dict[str, Any]]:
        """Get vertical performance trends."""
        pass