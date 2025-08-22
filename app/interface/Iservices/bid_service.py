from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from schemas.bid import (
    BidCreate, BidUpdate, BidResponse, BidListFilter, EnhancedBidFilter,
    BidStatusUpdate, BidStats, TeamBidStats, MemberBidRanking, 
    EarningsResponse, BidAnalytics, MemberRankingFilter, BulkOperationResult,
    DashboardSummary, MonthlyTrend
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import BidStatus, UserRole


class IBidService(ABC):
    """Interface for bid service operations."""
    
    # Basic CRUD operations
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
    def get_bids(self, db: Session, filters: BidListFilter, 
                requesting_user_id: UUID, requesting_user_role: UserRole,
                skip: int = 0, limit: int = 20, sort_by: str = "-submitted_at",
                requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[BidResponse]:
        """Get bids with filters and role-based access control."""
        pass
    
    @abstractmethod
    def get_bids_enhanced(self, db: Session, filters: EnhancedBidFilter, 
                         requesting_user_id: UUID, requesting_user_role: UserRole,
                         skip: int = 0, limit: int = 20,
                         requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[BidResponse]:
        """Get bids with enhanced filters and role-based access control."""
        pass
    
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
    
    # Role-based access methods
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
    
    # Statistics and analytics
    @abstractmethod
    def get_bid_statistics(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                          requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None,
                          date_from: Optional[datetime] = None,
                          date_to: Optional[datetime] = None) -> BidStats:
        """Get bid statistics with role-based filtering."""
        pass
    
    @abstractmethod
    def get_team_statistics(self, db: Session, team_id: Optional[UUID] = None,
                           requesting_user_role: UserRole = None,
                           requesting_user_team_id: Optional[UUID] = None) -> List[TeamBidStats]:
        """Get team bid statistics with role-based access."""
        pass
    
    @abstractmethod
    def get_member_rankings(self, db: Session, filters: MemberRankingFilter,
                           requesting_user_role: UserRole, 
                           requesting_user_team_id: Optional[UUID] = None,
                           skip: int = 0, limit: int = 20) -> PaginatedResponse[MemberBidRanking]:
        """Get member bid rankings with role-based access."""
        pass
    
    @abstractmethod
    def get_earnings(self, db: Session, team_id: Optional[UUID] = None,
                    member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                    requesting_user_role: UserRole = None,
                    requesting_user_team_id: Optional[UUID] = None,
                    date_from: Optional[datetime] = None,
                    date_to: Optional[datetime] = None) -> EarningsResponse:
        """Get earnings data with role-based access control."""
        pass
    
    @abstractmethod
    def get_bid_analytics(self, db: Session, team_id: Optional[UUID] = None,
                         member_id: Optional[UUID] = None,
                         requesting_user_role: UserRole = None,
                         requesting_user_team_id: Optional[UUID] = None,
                         date_from: Optional[datetime] = None,
                         date_to: Optional[datetime] = None) -> BidAnalytics:
        """Get advanced bid analytics with role-based access."""
        pass
    
    # Bulk operations
    @abstractmethod
    def bulk_update_status(self, db: Session, bid_ids: List[UUID], status: BidStatus,
                          requesting_user_id: UUID, requesting_user_role: UserRole,
                          requesting_user_team_id: Optional[UUID] = None) -> List[BidResponse]:
        """Bulk update bid status with permission checks."""
        pass
    
    @abstractmethod
    def bulk_delete_bids(self, db: Session, bid_ids: List[UUID],
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk delete bids with permission checks."""
        pass
    
    @abstractmethod
    def bulk_assign_team(self, db: Session, bid_ids: List[UUID], target_team_id: UUID,
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk assign bids to team (admin only)."""
        pass
    
    # Specialized queries
    @abstractmethod
    def get_recent_bids(self, db: Session,
                       requesting_user_id: UUID, requesting_user_role: UserRole, limit: int = 10,
                       requesting_user_team_id: Optional[UUID] = None) -> List[BidResponse]:
        """Get recent bids with role-based filtering."""
        pass
    
    @abstractmethod
    def get_winning_bids(self, db: Session, 
                        requesting_user_id: UUID, requesting_user_role: UserRole,skip: int = 0, limit: int = 20,
                        requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[BidResponse]:
        """Get winning bids with role-based filtering."""
        pass
    
    @abstractmethod
    def get_my_bids(self, db: Session, filters: BidListFilter,
                   requesting_user_id: UUID, skip: int = 0, limit: int = 20,
                   sort_by: str = "-submitted_at") -> PaginatedResponse[BidResponse]:
        """Get current user's bids (convenience method for members)."""
        pass
    
    @abstractmethod
    def get_dashboard_summary(self, db: Session, requesting_user_id: UUID,
                             requesting_user_role: UserRole,
                             requesting_user_team_id: Optional[UUID] = None) -> DashboardSummary:
        """Get bid summary for dashboard display based on user role."""
        pass
    
    @abstractmethod
    def get_top_performers(self, db: Session, team_id: Optional[UUID] = None,
                          limit: int = 5, requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None) -> List[MemberBidRanking]:
        """Get top performing members with role-based access."""
        pass
    
    @abstractmethod
    def get_monthly_trends(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None, months: int = 12,
                          requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None) -> List[MonthlyTrend]:
        """Get monthly bid trends with role-based access."""
        pass
    
    @abstractmethod
    def get_pending_bids_count(self, db: Session, requesting_user_id: UUID,
                              requesting_user_role: UserRole,
                              requesting_user_team_id: Optional[UUID] = None) -> int:
        """Get count of pending bids based on user role."""
        pass
    
    # Utility methods
    @abstractmethod
    def calculate_bid_costs(self, connects_used: int, boost_connects: int = 0) -> dict:
        """Calculate bid costs (connect cost, total cost)."""
        pass
    
    @abstractmethod
    def check_bid_edit_permission(self, db: Session, bid_id: UUID,
                                 requesting_user_id: UUID, requesting_user_role: UserRole) -> dict:
        """Check if current user can edit the specified bid with detailed response."""
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