from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from schemas.bid import (
    BidCreate, BidUpdate, BidResponse, BidListFilter, EnhancedBidFilter,
    TeamBidStats, MemberBidRanking, EarningsResponse, BidAnalytics,
    MemberRankingFilter, BulkOperationResult, MonthlyTrend
)
from schemas.common import PaginatedResponse
from models.models import Bid, BidStatus, UserRole


class IBidRepository(ABC):
    """Interface for bid repository operations."""
    
    # Basic CRUD operations
    @abstractmethod
    def create(self, db: Session, bid_data: BidCreate) -> Bid:
        """Create a new bid."""
        pass
    
    @abstractmethod
    def get_by_id(self, db: Session, bid_id: UUID) -> Optional[Bid]:
        """Get bid by ID with related data."""
        pass
    
    @abstractmethod
    def get_all(self, db: Session, filters: BidListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-submitted_at") -> PaginatedResponse:
        """Get all bids with filters and pagination."""
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
    
    # Role-based access methods
    @abstractmethod
    def get_bids_by_role(self, db: Session, filters: EnhancedBidFilter, 
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None,
                        skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get bids based on user role with enhanced filtering."""
        pass
    
    @abstractmethod
    def can_access_bid(self, db: Session, bid_id: UUID, user_id: UUID, 
                      user_role: UserRole, user_team_id: Optional[UUID] = None) -> bool:
        """Check if user can access specific bid."""
        pass
    
    @abstractmethod
    def can_modify_bid(self, db: Session, bid_id: UUID, user_id: UUID, 
                      user_role: UserRole, user_team_id: Optional[UUID] = None) -> bool:
        """Check if user can modify specific bid."""
        pass
    
    # Statistics and analytics
    @abstractmethod
    def get_statistics(self, db: Session, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get bid statistics."""
        pass
    
    @abstractmethod
    def get_team_statistics(self, db: Session, team_id: Optional[UUID] = None,
                           user_role: UserRole = None, 
                           requesting_user_team_id: Optional[UUID] = None) -> List[TeamBidStats]:
        """Get team bid statistics."""
        pass
    
    @abstractmethod
    def get_member_rankings(self, db: Session, filters: MemberRankingFilter,
                           user_role: UserRole, user_team_id: Optional[UUID] = None,
                           skip: int = 0, limit: int = 20) -> PaginatedResponse[MemberBidRanking]:
        """Get member bid rankings."""
        pass
    
    @abstractmethod
    def get_earnings(self, db: Session, team_id: Optional[UUID] = None,
                    member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                    date_from: Optional[datetime] = None, 
                    date_to: Optional[datetime] = None) -> EarningsResponse:
        """Get earnings data with breakdown."""
        pass
    
    @abstractmethod
    def get_bid_analytics(self, db: Session, team_id: Optional[UUID] = None,
                         member_id: Optional[UUID] = None,
                         date_from: Optional[datetime] = None,
                         date_to: Optional[datetime] = None) -> BidAnalytics:
        """Get advanced bid analytics."""
        pass
    
    @abstractmethod
    def get_monthly_trends(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None,
                          months: int = 12) -> List[MonthlyTrend]:
        """Get monthly bid trends."""
        pass
    
    # Bulk operations
    @abstractmethod
    def bulk_update_status(self, db: Session, bid_ids: List[UUID], 
                          status: BidStatus, user_id: UUID, user_role: UserRole,
                          user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk update bid status with permission checks."""
        pass
    
    @abstractmethod
    def bulk_delete(self, db: Session, bid_ids: List[UUID], 
                   user_id: UUID, user_role: UserRole,
                   user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk delete bids with permission checks."""
        pass
    
    @abstractmethod
    def bulk_assign_team(self, db: Session, bid_ids: List[UUID], 
                        target_team_id: UUID, user_id: UUID, user_role: UserRole,
                        user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk assign bids to team with permission checks."""
        pass
    
    # Specialized queries
    @abstractmethod
    def get_recent_bids(self, db: Session, limit: int = 10, 
                       team_id: Optional[UUID] = None,
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
    def get_pending_bids(self, db: Session, team_id: Optional[UUID] = None,
                        member_id: Optional[UUID] = None) -> List[Bid]:
        """Get pending bids (not viewed or viewed status)."""
        pass
    
    @abstractmethod
    def get_top_performers(self, db: Session, team_id: Optional[UUID] = None,
                          limit: int = 5) -> List[MemberBidRanking]:
        """Get top performing members."""
        pass
    
    @abstractmethod
    def get_bids_for_receivables(self, db: Session) -> List[Bid]:
        """Get won bids that don't have receivables yet."""
        pass
    
    @abstractmethod
    def get_performance_trends(self, db: Session, team_id: Optional[UUID] = None,
                              member_id: Optional[UUID] = None, 
                              days: int = 30) -> List[Dict[str, Any]]:
        """Get performance trends over time."""
        pass
    
    # Utility methods
    @abstractmethod
    def calculate_estimated_value(self, bid: Bid) -> Optional[float]:
        """Calculate estimated value for a bid."""
        pass
    
    @abstractmethod
    def can_edit(self, db: Session, bid_id: UUID, user_id: UUID) -> bool:
        """Check if user can edit the bid."""
        pass