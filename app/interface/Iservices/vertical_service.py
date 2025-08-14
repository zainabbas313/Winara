from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from abc import ABC, abstractmethod

from schemas.vertical import (
    VerticalCreate, VerticalUpdate, VerticalResponse,
    VerticalListFilter, VerticalStats
)
from schemas.common import SuccessResponse, PaginatedResponse


class IVerticalService(ABC):
    
    @abstractmethod
    def create_vertical(self, db: Session, vertical_data: VerticalCreate, created_by_id: UUID) -> VerticalResponse:
        pass

    @abstractmethod
    def get_vertical(self, db: Session, vertical_id: UUID) -> Optional[VerticalResponse]:
        pass

    @abstractmethod
    def get_verticals(self, db: Session, filters: VerticalListFilter, skip: int = 0,
                      limit: int = 20, sort_by: str = "sort_order") -> PaginatedResponse[VerticalResponse]:
        pass

    @abstractmethod
    def update_vertical(self, db: Session, vertical_id: UUID, vertical_data: VerticalUpdate) -> Optional[VerticalResponse]:
        pass

    @abstractmethod
    def delete_vertical(self, db: Session, vertical_id: UUID) -> SuccessResponse:
        pass

    @abstractmethod
    def get_children(self, db: Session, parent_id: UUID) -> List[VerticalResponse]:
        pass

    @abstractmethod
    def get_hierarchy(self, db: Session, vertical_id: UUID) -> List[VerticalResponse]:
        pass

    @abstractmethod
    def get_by_parent(self, db: Session, parent_id: Optional[UUID] = None) -> List[VerticalResponse]:
        pass

    @abstractmethod
    def get_statistics(self, db: Session, vertical_id: UUID, user_id: UUID,
                       user_role: str, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_performance_trends(self, db: Session, vertical_id: UUID, days: int = 30) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_top_performing(self, db: Session, limit: int = 10) -> List[VerticalResponse]:
        pass

    @abstractmethod
    def get_most_active(self, db: Session, limit: int = 10) -> List[VerticalResponse]:
        pass

    @abstractmethod
    def search(self, db: Session, query: str, limit: int = 20) -> List[VerticalResponse]:
        pass

    @abstractmethod
    def get_available_for_assignment(self, db: Session, user_id: UUID) -> List[VerticalResponse]:
        pass

    @abstractmethod
    def update_statistics(self, db: Session, vertical_id: UUID) -> None:
        pass

    @abstractmethod
    def update_sort_order(self, db: Session, vertical_id: UUID, new_order: int) -> bool:
        pass

    @abstractmethod
    def get_summary_statistics(self, db: Session) -> VerticalStats:
        pass

    @abstractmethod
    def bulk_activate(self, db: Session, vertical_ids: List[UUID]) -> int:
        pass

    @abstractmethod
    def bulk_deactivate(self, db: Session, vertical_ids: List[UUID]) -> int:
        pass
