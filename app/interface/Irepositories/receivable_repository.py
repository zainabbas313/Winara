from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from models.models import Receivable, ReceivableStatus
from schemas.receivable import (
    ReceivableCreate, ReceivableUpdate, ReceivableResponse, 
    ReceivableListFilter, ReceivableStatusUpdate, ReceivableStats
)
from schemas.common import PaginatedResponse, SuccessResponse


class IReceivableRepository(ABC):
    """Interface for receivable repository operations."""

    @abstractmethod
    def create(self, db: Session, receivable_data: ReceivableCreate, created_by_id: UUID) -> Receivable:
        """Create a new receivable."""
        pass

    @abstractmethod
    def get_by_id(self, db: Session, receivable_id: UUID) -> Optional[Receivable]:
        """Get receivable by ID with related data."""
        pass

    @abstractmethod
    def get_by_bid(self, db: Session, bid_id: UUID) -> Optional[Receivable]:
        """Get receivable by bid ID."""
        pass

    @abstractmethod
    def get_all(self, db: Session, filters: ReceivableListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get all receivables with filters and pagination."""
        pass

    @abstractmethod
    def get_by_team(self, db: Session, team_id: UUID, filters: ReceivableListFilter,
                   skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get receivables by team with filters."""
        pass

    @abstractmethod
    def get_by_status(self, db: Session, status: ReceivableStatus, 
                     skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get receivables by status."""
        pass

    @abstractmethod
    def update(self, db: Session, receivable_id: UUID, receivable_data: ReceivableUpdate) -> Optional[Receivable]:
        """Update receivable."""
        pass

    @abstractmethod
    def update_status(self, db: Session, receivable_id: UUID, status: ReceivableStatus) -> Optional[Receivable]:
        """Update receivable status."""
        pass

    @abstractmethod
    def delete(self, db: Session, receivable_id: UUID) -> bool:
        """Delete receivable."""
        pass

    @abstractmethod
    def get_overdue(self, db: Session, team_id: Optional[UUID] = None) -> List[Receivable]:
        """Get overdue receivables."""
        pass

    @abstractmethod
    def get_statistics(self, db: Session, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get receivable statistics."""
        pass

    @abstractmethod
    def get_team_statistics(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        """Get team receivable statistics."""
        pass

    @abstractmethod
    def get_monthly_summary(self, db: Session, year: int, month: int, 
                           team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get monthly receivables summary."""
        pass

    @abstractmethod
    def mark_overdue(self, db: Session) -> int:
        """Mark overdue receivables and return count."""
        pass

    @abstractmethod
    def get_payment_trends(self, db: Session, team_id: Optional[UUID] = None,
                          days: int = 90) -> List[Dict[str, Any]]:
        """Get payment trends over time."""
        pass

    @abstractmethod
    def get_client_summary(self, db: Session, team_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Get summary by client."""
        pass

    @abstractmethod
    def calculate_cash_flow(self, db: Session, team_id: Optional[UUID] = None,
                           days_ahead: int = 90) -> List[Dict[str, Any]]:
        """Calculate projected cash flow."""
        pass

