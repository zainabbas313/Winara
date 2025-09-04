from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from models.models import ProjectModule, Receivable, ReceivableStatus
from schemas.receivable import (
    ProjectModuleCreate, ReceivableCreate, ReceivableUpdate, ReceivableResponse, 
    ReceivableListFilter, ReceivableStatusUpdate, ReceivableStats
)
from schemas.common import PaginatedResponse, SuccessResponse


class IReceivableRepository(ABC):
    """Interface for receivable repository operations."""

    @abstractmethod
    def create(self, db: Session, receivable_data: ReceivableCreate, created_by_id: UUID) -> Receivable:
        pass

    @abstractmethod
    def create_module(self, db: Session, bid_id: UUID, module_data: ProjectModuleCreate) -> ProjectModule:
        pass

    @abstractmethod
    def create_bulk_modules_and_receivables(
        self, db: Session, bid_id: UUID, modules_data: List[ProjectModuleCreate],
        created_by_id: UUID, currency: str = "USD"
    ) -> List[Receivable]:
        pass

    @abstractmethod
    def get_by_id(self, db: Session, receivable_id: UUID) -> Optional[Receivable]:
        pass

    @abstractmethod
    def get_by_bid(self, db: Session, bid_id: UUID) -> List[Receivable]:
        pass

    @abstractmethod
    def get_by_module(self, db: Session, module_id: UUID) -> Optional[Receivable]:
        pass

    @abstractmethod
    def get_all(self, db: Session, filters: ReceivableListFilter, skip: int = 0,
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        pass

    @abstractmethod
    def get_by_team(self, db: Session, team_id: UUID, filters: ReceivableListFilter,
                    skip: int = 0, limit: int = 20) -> PaginatedResponse:
        pass

    @abstractmethod
    def get_by_status(self, db: Session, status: ReceivableStatus,
                      skip: int = 0, limit: int = 20) -> PaginatedResponse:
        pass

    @abstractmethod
    def update(self, db: Session, receivable_id: UUID, receivable_data: ReceivableUpdate) -> Optional[Receivable]:
        pass

    @abstractmethod
    def update_status(self, db: Session, receivable_id: UUID, status: ReceivableStatus) -> Optional[Receivable]:
        pass

    @abstractmethod
    def delete(self, db: Session, receivable_id: UUID) -> bool:
        pass

    @abstractmethod
    def get_overdue(self, db: Session, team_id: Optional[UUID] = None) -> List[Receivable]:
        pass

    @abstractmethod
    def get_statistics(self, db: Session, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_team_statistics(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_monthly_summary(self, db: Session, year: int, month: int,
                            team_id: Optional[UUID] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def mark_overdue(self, db: Session) -> int:
        pass

    @abstractmethod
    def get_payment_trends(self, db: Session, team_id: Optional[UUID] = None,
                           days: int = 90) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_client_summary(self, db: Session, team_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def calculate_cash_flow(self, db: Session, team_id: Optional[UUID] = None,
                            days_ahead: int = 90) -> List[Dict[str, Any]]:
        pass
