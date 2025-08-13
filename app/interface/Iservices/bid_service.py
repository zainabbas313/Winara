from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.bid import (
    BidCreate, BidUpdate, BidResponse, BidListFilter, 
    BidStatusUpdate, BidStats
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import BidStatus, UserRole


class IBidService(ABC):
    
    @abstractmethod
    def create_bid(self, db: Session, bid_data: BidCreate, 
                  requesting_user_id: UUID, requesting_user_role: UserRole,
                  requesting_user_team_id: Optional[UUID] = None) -> BidResponse:
        """Create a new bid with validation and permission checks."""
        pass
    
    @abstractmethod
    def get_bid(self, db: Session, bid_id: UUID,
               requesting_user_id: UUID, requesting_user_role: UserRole,
               requesting_user_team_id: Optional[UUID] = None) -> Optional[BidResponse]:
        """Get bid by ID with role-based access control."""
        pass
    
    @abstractmethod
    def get_bids(
        self,
        db: Session,
        filters: BidListFilter,
        requesting_user_id: UUID,
        requesting_user_role: UserRole,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "-submitted_at",
        requesting_user_team_id: Optional[UUID] = None
    ) -> PaginatedResponse[BidResponse]:
        """Get bids with filters and role-based access control."""

    
    @abstractmethod
    def update_bid(self, db: Session, bid_id: UUID, bid_data: BidUpdate,
                  requesting_user_id: UUID, requesting_user_role: UserRole,
                  requesting_user_team_id: Optional[UUID] = None) -> Optional[BidResponse]:
        """Update bid with validation and permission checks."""
        pass
    
    @abstractmethod
    def update_bid_status(self, db: Session, bid_id: UUID, status_data: BidStatusUpdate,
                         requesting_user_id: UUID, requesting_user_role: UserRole,
                         requesting_user_team_id: Optional[UUID] = None) -> Optional[BidResponse]:
        """Update bid status with permission checks."""
        pass
    
    @abstractmethod
    def delete_bid(self, db: Session, bid_id: UUID,
                  requesting_user_id: UUID, requesting_user_role: UserRole,
                  requesting_user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Delete bid with permission checks."""
        pass
    
    @abstractmethod
    def validate_bid_access(self, db: Session, bid_id: UUID,
                           requesting_user_id: UUID, requesting_user_role: UserRole,
                           requesting_user_team_id: Optional[UUID] = None) -> bool:
        """Validate if user has access to the bid."""
        pass
    
    @abstractmethod
    def validate_bid_edit_permission(self, db: Session, bid_id: UUID,
                                    requesting_user_id: UUID, requesting_user_role: UserRole) -> bool:
        """Validate if user can edit the bid (considering 5-day rule)."""
        pass
    
    @abstractmethod
    def validate_vertical_assignment(self, db: Session, user_id: UUID, vertical_id: UUID) -> bool:
        """Validate if user is assigned to the vertical."""
        pass
    
    @abstractmethod
    def calculate_bid_costs(self, connects_used: int, boost_connects: int = 0) -> dict:
        """Calculate bid costs (connect cost, total cost)."""
        pass
    
    @abstractmethod
    def get_bid_statistics(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                          requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None) -> BidStats:
        """Get bid statistics with role-based filtering."""
        pass
    
    @abstractmethod
    def bulk_update_status(self, db: Session, bid_ids: List[UUID], status: BidStatus,
                          requesting_user_id: UUID, requesting_user_role: UserRole,
                          requesting_user_team_id: Optional[UUID] = None) -> List[BidResponse]:
        """Bulk update bid status with permission checks."""
        pass
    
    @abstractmethod
    def get_recent_bids(self, db: Session,  requesting_user_id: UUID, requesting_user_role: UserRole, limit: int = 10,
                       requesting_user_team_id: Optional[UUID] = None) -> List[BidResponse]:
        """Get recent bids with role-based filtering."""
        pass
    
    @abstractmethod
    def get_winning_bids(self, db: Session,
                        requesting_user_id: UUID, requesting_user_role: UserRole, skip: int = 0, limit: int = 20,
                        requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[BidResponse]:
        """Get winning bids with role-based filtering."""
        pass
    
    @abstractmethod
    def create_bid_notification(self, db: Session, bid_id: UUID, 
                               old_status: Optional[BidStatus] = None,
                               new_status: Optional[BidStatus] = None) -> None:
        """Create notifications for bid status changes."""
        pass
    
    @abstractmethod
    def auto_create_receivable(self, db: Session, bid_id: UUID) -> None:
        """Automatically create receivable for won bids."""
        pass