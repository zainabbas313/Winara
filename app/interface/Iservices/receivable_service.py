# interface/Iservices/receivable_service.py
from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session

from schemas.receivable import (
    ReceivableCreate, ReceivableUpdate, ReceivableResponse, ReceivableListFilter,
    ReceivableStatusUpdate, ReceivableStats, BidReceivableResponse, ProjectModuleResponse
)
from schemas.common import SuccessResponse, PaginatedResponse


class IReceivableService(ABC):
    """Interface for Receivable Service."""

    @abstractmethod
    def create_receivable(self, db: Session, receivable_data: ReceivableCreate,
                          created_by_id: UUID, user_role: str,
                          user_team_id: Optional[UUID] = None) -> ReceivableResponse:
        pass

    @abstractmethod
    def get_receivable(self, db: Session, receivable_id: UUID, user_id: UUID,
                       user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        pass

    @abstractmethod
    def get_module_receivable(self, db: Session, module_id: UUID, user_id: UUID,
                              user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        pass

    @abstractmethod
    def get_bid_receivables(self, db: Session, bid_id: UUID, user_id: UUID,
                            user_role: str, user_team_id: Optional[UUID] = None) -> BidReceivableResponse:
        pass

    @abstractmethod
    def get_receivables(self, db: Session, filters: ReceivableListFilter, user_id: UUID, user_role: str,
                        skip: int = 0, limit: int = 20, sort_by: str = "-created_at",
                        user_team_id: Optional[UUID] = None) -> PaginatedResponse[ReceivableResponse]:
        pass

    @abstractmethod
    def update_receivable(self, db: Session, receivable_id: UUID, receivable_data: ReceivableUpdate,
                          user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        pass

    @abstractmethod
    def update_receivable_status(self, db: Session, receivable_id: UUID, status_data: ReceivableStatusUpdate,
                                 user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        pass

    @abstractmethod
    def delete_receivable(self, db: Session, receivable_id: UUID, user_id: UUID,
                          user_role: str, user_team_id: Optional[UUID] = None) -> SuccessResponse:
        pass

    @abstractmethod
    def get_overdue_receivables(self, db: Session, team_id: Optional[UUID] = None) -> List[ReceivableResponse]:
        pass

    @abstractmethod
    def get_statistics(self, db: Session, team_id: Optional[UUID] = None) -> ReceivableStats:
        pass

    @abstractmethod
    def mark_overdue_receivables(self, db: Session) -> int:
        pass
