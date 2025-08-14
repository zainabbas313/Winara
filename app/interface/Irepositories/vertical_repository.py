from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.vertical import VerticalCreate, VerticalUpdate, VerticalListFilter
from schemas.common import PaginatedResponse
from models.models import Vertical


class IVerticalRepository(ABC):
    """Interface for Vertical repository operations."""

    @abstractmethod
    def create(self, db: Session, vertical_data: VerticalCreate, created_by_id: UUID) -> Vertical:
        pass

    @abstractmethod
    def get_by_id(self, db: Session, vertical_id: UUID) -> Optional[Vertical]:
        pass

    @abstractmethod
    def get_by_slug(self, db: Session, slug: str) -> Optional[Vertical]:
        pass

    @abstractmethod
    def get_all(self, db: Session, filters: VerticalListFilter, skip: int = 0,
                limit: int = 20, sort_by: str = "sort_order") -> PaginatedResponse:
        pass

    @abstractmethod
    def get_by_parent(self, db: Session, parent_id: Optional[UUID] = None) -> List[Vertical]:
        pass

    @abstractmethod
    def get_children(self, db: Session, parent_id: UUID) -> List[Vertical]:
        pass

    @abstractmethod
    def get_hierarchy(self, db: Session, vertical_id: UUID) -> List[Vertical]:
        pass

    @abstractmethod
    def update(self, db: Session, vertical_id: UUID, vertical_data: VerticalUpdate) -> Optional[Vertical]:
        pass

    @abstractmethod
    def delete(self, db: Session, vertical_id: UUID) -> bool:
        pass

    @abstractmethod
    def update_statistics(self, db: Session, vertical_id: UUID) -> None:
        pass

    @abstractmethod
    def get_statistics(self, db: Session, vertical_id: UUID) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_top_performing(self, db: Session, limit: int = 10) -> List[Vertical]:
        pass

    @abstractmethod
    def get_most_active(self, db: Session, limit: int = 10) -> List[Vertical]:
        pass

    @abstractmethod
    def search(self, db: Session, query: str, limit: int = 20) -> List[Vertical]:
        pass

    @abstractmethod
    def get_available_for_assignment(self, db: Session, user_id: UUID) -> List[Vertical]:
        pass

    @abstractmethod
    def update_sort_order(self, db: Session, vertical_id: UUID, new_order: int) -> bool:
        pass

    @abstractmethod
    def get_performance_trends(self, db: Session, vertical_id: UUID, days: int = 30) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def bulk_update_status(self, db: Session, vertical_ids: List[UUID], is_active: bool) -> int:
        pass
