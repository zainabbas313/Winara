from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.receivable import (
    ReceivableCreate, ReceivableUpdate, ReceivableResponse, ReceivableListFilter,
    ReceivableStatusUpdate, ReceivableStats
)
from schemas.common import SuccessResponse, PaginatedResponse


class IReceivableService(ABC):
    
    @abstractmethod
    def create_receivable(self, db: Session, receivable_data: ReceivableCreate, 
                         created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> ReceivableResponse:
        """Create a new receivable."""
        pass
    
    @abstractmethod
    def get_receivable(self, db: Session, receivable_id: UUID, user_id: UUID,
                      user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        """Get receivable by ID with access control."""
        pass
    
    @abstractmethod
    def get_receivables(self, db: Session, filters: ReceivableListFilter,  user_id: UUID,
                       user_role: str, skip: int = 0,
                       limit: int = 20, sort_by: str = "-created_at",user_team_id: Optional[UUID] = None) -> PaginatedResponse[ReceivableResponse]:
        """Get receivables with filtering, pagination and access control."""
        pass
    
    @abstractmethod
    def update_receivable(self, db: Session, receivable_id: UUID, receivable_data: ReceivableUpdate,
                         user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        """Update receivable with access control."""
        pass
    
    @abstractmethod
    def update_receivable_status(self, db: Session, receivable_id: UUID, status_data: ReceivableStatusUpdate,
                                user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        """Update receivable status with access control."""
        pass
    
    @abstractmethod
    def delete_receivable(self, db: Session, receivable_id: UUID, user_id: UUID,
                         user_role: str, user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Delete receivable with access control."""
        pass
    
    @abstractmethod
    def get_overdue_receivables(self, db: Session, team_id: Optional[UUID] = None) -> List[ReceivableResponse]:
        """Get overdue receivables."""
        pass
    
    @abstractmethod
    def get_statistics(self, db: Session, team_id: Optional[UUID] = None) -> ReceivableStats:
        """Get receivable statistics."""
        pass
    
    @abstractmethod
    def get_monthly_summary(self, db: Session, year: int, month: int, 
                           team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get monthly receivables summary."""
        pass
    
    @abstractmethod
    def get_payment_trends(self, db: Session, team_id: Optional[UUID] = None,
                          days: int = 90) -> List[Dict[str, Any]]:
        """Get payment trends over specified period."""
        pass
    
    @abstractmethod
    def get_client_summary(self, db: Session, team_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Get summary statistics by client."""
        pass
    
    @abstractmethod
    def calculate_cash_flow(self, db: Session, team_id: Optional[UUID] = None,
                           days_ahead: int = 90) -> List[Dict[str, Any]]:
        """Calculate projected cash flow based on expected payment dates."""
        pass
    
    @abstractmethod
    def mark_overdue_receivables(self, db: Session) -> int:
        """Mark overdue receivables and return count."""
        pass