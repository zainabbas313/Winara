from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.models import Bid, BidStatus
from schemas.bid import BidCreate, BidUpdate, BidListFilter
from schemas.common import PaginatedResponse


class IBidRepository(ABC):
    
    @abstractmethod
    def create(self, db: Session, bid_data: BidCreate) -> Bid:
        """Create a new bid."""
        pass
    
    @abstractmethod
    def get_by_id(self, db: Session, bid_id: UUID) -> Optional[Bid]:
        """Get bid by ID."""
        pass
    
    @abstractmethod
    def get_all(self, db: Session, filters: BidListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-submitted_at") -> PaginatedResponse:
        """Get all bids with filters and pagination."""
        pass
    
    @abstractmethod
    def get_by_member(self, db: Session, member_id: UUID, filters: BidListFilter,
                     skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get bids by member with filters."""
        pass
    
    @abstractmethod
    def get_by_team(self, db: Session, team_id: UUID, filters: BidListFilter,
                   skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get bids by team with filters."""
        pass
    
    @abstractmethod
    def get_by_vertical(self, db: Session, vertical_id: UUID, skip: int = 0, 
                       limit: int = 20) -> PaginatedResponse:
        """Get bids by vertical."""
        pass
    
    @abstractmethod
    def update(self, db: Session, bid_id: UUID, bid_data: BidUpdate) -> Optional[Bid]:
        """Update bid."""
        pass
    
    @abstractmethod
    def update_status(self, db: Session, bid_id: UUID, status: BidStatus) -> Optional[Bid]:
        """Update bid status."""
        pass
    
    @abstractmethod
    def delete(self, db: Session, bid_id: UUID) -> bool:
        """Delete bid."""
        pass
    
    @abstractmethod
    def can_edit(self, db: Session, bid_id: UUID, user_id: UUID) -> bool:
        """Check if user can edit the bid."""
        pass
    
    @abstractmethod
    def get_statistics(self, db: Session, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get bid statistics."""
        pass
    
    @abstractmethod
    def get_team_statistics(self, db: Session, team_id: UUID, 
                           filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get team bid statistics."""
        pass
    
    @abstractmethod
    def get_member_statistics(self, db: Session, member_id: UUID,
                             filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get member bid statistics."""
        pass
    
    @abstractmethod
    def get_vertical_statistics(self, db: Session, vertical_id: UUID,
                               filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get vertical bid statistics."""
        pass
    
    @abstractmethod
    def get_recent_bids(self, db: Session, limit: int = 10, team_id: Optional[UUID] = None,
                       member_id: Optional[UUID] = None) -> List[Bid]:
        """Get recent bids."""
        pass
    
    @abstractmethod
    def get_winning_bids(self, db: Session, team_id: Optional[UUID] = None,
                        member_id: Optional[UUID] = None, skip: int = 0, 
                        limit: int = 20) -> PaginatedResponse:
        """Get winning bids."""
        pass
    
    @abstractmethod
    def bulk_update_status(self, db: Session, bid_ids: List[UUID], 
                          status: BidStatus) -> List[Bid]:
        """Bulk update bid status."""
        pass
    
    @abstractmethod
    def get_bids_for_receivables(self, db: Session) -> List[Bid]:
        """Get won bids that don't have receivables yet."""
        pass
    
    @abstractmethod
    def calculate_estimated_value(self, bid: Bid) -> Optional[float]:
        """Calculate estimated value for a bid."""
        pass
    
    @abstractmethod
    def get_performance_trends(self, db: Session, team_id: Optional[UUID] = None,
                              member_id: Optional[UUID] = None, 
                              days: int = 30) -> List[Dict[str, Any]]:
        """Get performance trends over time."""
        pass