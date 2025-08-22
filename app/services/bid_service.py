from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from interface.Iservices.bid_service import IBidService
from repositories.bid_repository import BidRepository
from repositories.user_repository import UserRepository
from repositories.notification_repository import NotificationRepository
from repositories.audit_repository import AuditRepository
from repositories.team_repository import TeamRepository
from schemas.bid import (
    BidCreate, BidDerived, BidUpdate, BidResponse, BidListFilter, EnhancedBidFilter,
    BidStatusUpdate, BidStats, TeamBidStats, MemberBidRanking, EarningsResponse,
    BidAnalytics, MemberRankingFilter, BulkOperationResult, DashboardSummary,
    BidSummary, MonthlyTrend
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import BidStatus, UserRole, AuditAction
from utils.helpers import (
    calculate_connect_cost, estimate_project_value, 
    can_edit_bid, calculate_days_since
)
from utils.validators import validate_connects_usage, validate_budget_consistency
import logging

logger = logging.getLogger(__name__)


class BidService(IBidService):
    def __init__(self):
        self.bid_repo = BidRepository()
        self.team_repo = TeamRepository()
        self.user_repo = UserRepository()
        self.notification_repo = NotificationRepository()
        self.audit_repo = AuditRepository()

    def create_bid(self, db: Session, bid_data: BidCreate, 
                  requesting_user_id: UUID, requesting_user_role: UserRole,
                  requesting_user_team_id: Optional[UUID] = None) -> BidResponse:
        """Create a new bid with validation and permission checks."""
        try:
            # Validate team_id requirement based on user role
            if requesting_user_role in [UserRole.SUB_ADMIN, UserRole.MEMBER]:
                if not bid_data.team_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="team_id is required for sub-admin and member users"
                    )
            
            # Validate user permissions
            if not self._validate_bid_creation_permission(
                db, bid_data, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to create bid for this team"
                )
            
            # Validate vertical assignment
            if requesting_user_role != UserRole.ADMIN:
                if not self.validate_vertical_assignment(db, requesting_user_id, bid_data.vertical_id):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="User is not assigned to this vertical"
                    )
            
            # Validate connects usage
            is_valid, error_msg = validate_connects_usage(
                bid_data.connects_used, bid_data.boost_connects_used
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
            
            # Validate budget consistency
            is_valid, errors = validate_budget_consistency(
                bid_data.budget_type.value, bid_data.budget_min,
                bid_data.budget_max, bid_data.hourly_rate
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Budget validation failed: {', '.join(errors)}"
                )
            
            # Set member_id
            bid_data.member_id = requesting_user_id
            
            # Create bid
            bid = self.bid_repo.create(db, bid_data)
            
            # Log bid creation
            self.audit_repo.create_audit_log(
                db, AuditAction.CREATE, "bid", bid.id, requesting_user_id, None,
                None, None, f"Bid created: {bid.job_title}",
                old_values={},
                new_values={
                    "job_title": bid.job_title,
                    "vertical_id": str(bid.vertical_id),
                    "budget_type": bid.budget_type.value,
                    "connects_used": bid.connects_used,
                    "total_cost": str(bid.total_cost)
                }
            )
            
            return self._build_bid_response(bid)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating bid: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Bid creation failed"
            )

    def get_bid(self, db: Session, bid_id: UUID,
               requesting_user_id: UUID, requesting_user_role: UserRole,
               requesting_user_team_id: Optional[UUID] = None) -> Optional[BidResponse]:
        """Get bid by ID with role-based access control."""
        try:
            print(f"{bid_id}-{requesting_user_id}-{requesting_user_role}-{requesting_user_team_id}")
            if not self.bid_repo.can_access_bid(
                db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view this bid"
                )
            
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                return None
            
            return self._build_bid_response(bid)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bid {bid_id}: {e}")
            return None

    def get_bids(self, db: Session, filters: BidListFilter, 
                requesting_user_id: UUID, requesting_user_role: UserRole,
                skip: int = 0, limit: int = 20, sort_by: str = "-submitted_at",
                requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[BidResponse]:
        """Get bids with filters and role-based access control."""
        try:
            # Apply role-based filtering
            filtered_filters = self._apply_role_based_filters(
                filters, requesting_user_role, requesting_user_id, requesting_user_team_id
            )
            
            # Get bids
            result = self.bid_repo.get_all(db, filtered_filters, skip, limit, sort_by)
            
            # Convert to response objects
            bid_responses = [self._build_bid_response(bid) for bid in result.items]
            
            return PaginatedResponse(
                items=bid_responses,
                next_cursor=result.next_cursor,
                count=result.count
            )
            
        except Exception as e:
            logger.error(f"Error getting bids: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_bids_enhanced(self, db: Session, filters: EnhancedBidFilter, 
                         requesting_user_id: UUID, requesting_user_role: UserRole,
                         skip: int = 0, limit: int = 20,
                         requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[BidResponse]:
        """Get bids with enhanced filters and role-based access control."""
        try:
            result = self.bid_repo.get_bids_by_role(
                db, filters, requesting_user_id, requesting_user_role,
                requesting_user_team_id, skip, limit
            )
            
            bid_responses = [self._build_bid_response(bid) for bid in result.items]
            
            return PaginatedResponse(
                items=bid_responses,
                next_cursor=result.next_cursor,
                count=result.count
            )
            
        except Exception as e:
            logger.error(f"Error getting bids with enhanced filters: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def update_bid(self, db: Session, bid_id: UUID, bid_data: BidUpdate,
                  requesting_user_id: UUID, requesting_user_role: UserRole,
                  requesting_user_team_id: Optional[UUID] = None) -> Optional[BidResponse]:
        """Update bid with validation and permission checks."""
        try:
            # Check if bid exists and user can modify it
            if not self.bid_repo.can_modify_bid(
                db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot edit this bid (edit window expired or insufficient permissions)"
                )
            
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bid not found"
                )
            
            # Store old values for audit
            old_values = {
                "job_title": bid.job_title,
                "budget_type": bid.budget_type.value,
                "connects_used": bid.connects_used,
                "status": bid.status.value
            }
            
            # Validate budget consistency if budget fields are being updated
            if any([bid_data.budget_type, bid_data.budget_min, bid_data.budget_max, bid_data.hourly_rate]):
                budget_type = bid_data.budget_type.value if bid_data.budget_type else bid.budget_type.value
                budget_min = bid_data.budget_min if bid_data.budget_min is not None else bid.budget_min
                budget_max = bid_data.budget_max if bid_data.budget_max is not None else bid.budget_max
                hourly_rate = bid_data.hourly_rate if bid_data.hourly_rate is not None else bid.hourly_rate
                
                is_valid, errors = validate_budget_consistency(
                    budget_type, budget_min, budget_max, hourly_rate
                )
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Budget validation failed: {', '.join(errors)}"
                    )
            
            # Validate connects usage if being updated
            if bid_data.connects_used is not None or bid_data.boost_connects_used is not None:
                connects = bid_data.connects_used if bid_data.connects_used is not None else bid.connects_used
                boost_connects = bid_data.boost_connects_used if bid_data.boost_connects_used is not None else bid.boost_connects_used
                
                is_valid, error_msg = validate_connects_usage(connects, boost_connects)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )
            
            # Update bid
            updated_bid = self.bid_repo.update(db, bid_id, bid_data)
            if not updated_bid:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Bid update failed"
                )
            
            # Create new values for audit
            new_values = {
                "job_title": updated_bid.job_title,
                "budget_type": updated_bid.budget_type.value,
                "connects_used": updated_bid.connects_used,
                "status": updated_bid.status.value
            }
            
            # Log bid update
            self.audit_repo.create_audit_log(
                db, AuditAction.UPDATE, "bid", bid_id, requesting_user_id, None,
                None, None, f"Bid updated: {updated_bid.job_title}",
                old_values=old_values,
                new_values=new_values
            )
            
            return self._build_bid_response(updated_bid)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating bid {bid_id}: {e}")
            return None

    def update_bid_status(self, db: Session, bid_id: UUID, status_data: BidStatusUpdate,
                         requesting_user_id: UUID, requesting_user_role: UserRole,
                         requesting_user_team_id: Optional[UUID] = None) -> Optional[BidResponse]:
        """Update bid status with permission checks."""
        try:
            # Validate access
            if not self.bid_repo.can_access_bid(
                db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to update bid status"
                )
            
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bid not found"
                )
            
            old_status = bid.status
            
            # Update status
            updated_bid = self.bid_repo.update_status(db, bid_id, status_data.status)
            if not updated_bid:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Status update failed"
                )
            
            # Log status change
            self.audit_repo.create_audit_log(
                db, AuditAction.STATUS_CHANGE, "bid", bid_id, requesting_user_id, None,
                None, None, f"Bid status changed: {old_status.value} -> {status_data.status.value}",
                old_values={"status": old_status.value},
                new_values={"status": status_data.status.value}
            )
            
            # Create notifications for status changes
            self.create_bid_notification(db, bid_id, old_status, status_data.status)
            
            # Auto-create receivable if bid is won
            if status_data.status == BidStatus.WON:
                self.auto_create_receivable(db, bid_id)
            
            return self._build_bid_response(updated_bid)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating bid status {bid_id}: {e}")
            return None

    def delete_bid(self, db: Session, bid_id: UUID,
                  requesting_user_id: UUID, requesting_user_role: UserRole,
                  requesting_user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Delete bid with permission checks."""
        try:
            # Validate delete permissions (stricter than edit)
            if not self.bid_repo.can_modify_bid(
                db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete this bid (insufficient permissions or bid has progressed)"
                )
            
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bid not found"
                )
            
            # Additional delete validation for members
            if requesting_user_role == UserRole.MEMBER:
                if bid.status != BidStatus.NOT_VIEWED:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot delete bid that has been viewed"
                    )
            
            # Store bid info for audit
            bid_info = {
                "job_title": bid.job_title,
                "member_id": str(bid.member_id),
                "team_id": str(bid.team_id),
                "status": bid.status.value
            }
            
            # Delete bid
            success = self.bid_repo.delete(db, bid_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Bid deletion failed"
                )
            
            # Log deletion
            self.audit_repo.create_audit_log(
                db, AuditAction.DELETE, "bid", bid_id, requesting_user_id, None,
                None, None, f"Bid deleted: {bid_info['job_title']}",
                old_values=bid_info, new_values={}
            )
            
            return SuccessResponse(message="Bid deleted successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting bid {bid_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Bid deletion failed"
            )

    def validate_bid_access(self, db: Session, bid_id: UUID,
                           requesting_user_id: UUID, requesting_user_role: UserRole,
                           requesting_user_team_id: Optional[UUID] = None) -> bool:
        """Validate if user has access to the bid."""
        return self.bid_repo.can_access_bid(
            db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
        )

    def validate_bid_edit_permission(self, db: Session, bid_id: UUID,
                                    requesting_user_id: UUID, requesting_user_role: UserRole) -> bool:
        """Validate if user can edit the bid (considering 5-day rule)."""
        return self.bid_repo.can_modify_bid(
            db, bid_id, requesting_user_id, requesting_user_role
        )

    def validate_vertical_assignment(self, db: Session, user_id: UUID, vertical_id: UUID) -> bool:
        """Validate if user is assigned to the vertical."""
        return self.user_repo.check_vertical_assignment(db, user_id, vertical_id)

    def get_bid_statistics(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                          requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None,
                          date_from: Optional[datetime] = None,
                          date_to: Optional[datetime] = None) -> BidStats:
        """Get bid statistics with role-based filtering."""
        try:
            filters = {}
            
            # Apply role-based filtering
            if requesting_user_role == UserRole.MEMBER and member_id:
                # Members can only see their own stats
                filters['member_id'] = member_id
            elif requesting_user_role == UserRole.SUB_ADMIN:
                # Sub-admins can only see their team stats
                filters['team_id'] = requesting_user_team_id
                if member_id:
                    # Validate member belongs to their team
                    member = self.user_repo.get_by_id(db, member_id)
                    if member and member.team_id == requesting_user_team_id:
                        filters['member_id'] = member_id
            elif requesting_user_role == UserRole.ADMIN:
                # Admins can see all stats
                if team_id:
                    filters['team_id'] = team_id
                if member_id:
                    filters['member_id'] = member_id
            
            if vertical_id:
                filters['vertical_id'] = vertical_id
            if date_from:
                filters['date_from'] = date_from
            if date_to:
                filters['date_to'] = date_to
            
            stats = self.bid_repo.get_statistics(db, filters)
            
            return BidStats(
                total_bids=stats.get('total_bids', 0),
                wins=stats.get('wins', 0),
                win_rate=stats.get('win_rate', 0),
                total_connects_used=stats.get('total_connects_used', 0),
                total_cost=stats.get('total_cost', 0),
                avg_response_time_hours=stats.get('avg_response_time_hours')
            )
            
        except Exception as e:
            logger.error(f"Error getting bid statistics: {e}")
            return BidStats(
                total_bids=0, wins=0, win_rate=0,
                total_connects_used=0, total_cost=0
            )

    def get_team_statistics(self, db: Session, team_id: Optional[UUID] = None,
                           requesting_user_role: UserRole = None,
                           requesting_user_team_id: Optional[UUID] = None) -> List[TeamBidStats]:
        """Get team bid statistics with role-based access."""
        try:
            return self.bid_repo.get_team_statistics(
                db, team_id, requesting_user_role, requesting_user_team_id
            )
        except Exception as e:
            logger.error(f"Error getting team statistics: {e}")
            return []

    def get_member_rankings(self, db: Session, filters: MemberRankingFilter,
                           requesting_user_role: UserRole, 
                           requesting_user_team_id: Optional[UUID] = None,
                           skip: int = 0, limit: int = 20) -> PaginatedResponse[MemberBidRanking]:
        """Get member bid rankings with role-based access."""
        try:
            # Apply role-based filtering to filters
            if requesting_user_role == UserRole.SUB_ADMIN:
                filters.team_id = requesting_user_team_id
            
            return self.bid_repo.get_member_rankings(
                db, filters, requesting_user_role, requesting_user_team_id, skip, limit
            )
        except Exception as e:
            logger.error(f"Error getting member rankings: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_earnings(self, db: Session, team_id: Optional[UUID] = None,
                    member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                    requesting_user_role: UserRole = None,
                    requesting_user_team_id: Optional[UUID] = None,
                    date_from: Optional[datetime] = None,
                    date_to: Optional[datetime] = None) -> EarningsResponse:
        """Get earnings data with role-based access control."""
        try:
            # Apply role-based filtering
            if requesting_user_role == UserRole.MEMBER and member_id:
                # Members can only see their own earnings
                pass  # member_id already set
            elif requesting_user_role == UserRole.SUB_ADMIN:
                # Sub-admins can only see their team earnings
                team_id = requesting_user_team_id
                if member_id:
                    # Validate member belongs to their team
                    member = self.user_repo.get_by_id(db, member_id)
                    if not member or member.team_id != requesting_user_team_id:
                        member_id = None  # Reset if invalid
            
            return self.bid_repo.get_earnings(
                db, team_id, member_id, vertical_id, date_from, date_to
            )
        except Exception as e:
            logger.error(f"Error getting earnings: {e}")
            return EarningsResponse(
                total_earnings=0, won_bids_count=0, avg_earnings_per_bid=0
            )

    def get_bid_analytics(self, db: Session, team_id: Optional[UUID] = None,
                         member_id: Optional[UUID] = None,
                         requesting_user_role: UserRole = None,
                         requesting_user_team_id: Optional[UUID] = None,
                         date_from: Optional[datetime] = None,
                         date_to: Optional[datetime] = None) -> BidAnalytics:
        """Get advanced bid analytics with role-based access."""
        try:
            # Apply role-based filtering
            if requesting_user_role == UserRole.MEMBER and member_id:
                pass  # member_id already set
            elif requesting_user_role == UserRole.SUB_ADMIN:
                team_id = requesting_user_team_id
                if member_id:
                    member = self.user_repo.get_by_id(db, member_id)
                    if not member or member.team_id != requesting_user_team_id:
                        member_id = None
            
            return self.bid_repo.get_bid_analytics(
                db, team_id, member_id, date_from, date_to
            )
        except Exception as e:
            logger.error(f"Error getting bid analytics: {e}")
            return BidAnalytics(
                conversion_rate=0, top_verticals=[], monthly_trends=[], performance_metrics={}
            )

    def bulk_update_status(self, db: Session, bid_ids: List[UUID], status: BidStatus,
                          requesting_user_id: UUID, requesting_user_role: UserRole,
                          requesting_user_team_id: Optional[UUID] = None) -> List[BidResponse]:
        """Bulk update bid status with permission checks."""
        try:
            result = self.bid_repo.bulk_update_status(
                db, bid_ids, status, requesting_user_id, requesting_user_role, requesting_user_team_id
            )
            
            # Convert updated bids to response objects
            bid_responses = []
            for bid_id in bid_ids:
                if any(str(bid.id) == str(bid_id) for bid in result.updated_bids if hasattr(result, 'updated_bids')):
                    bid = self.bid_repo.get_by_id(db, bid_id)
                    if bid:
                        bid_responses.append(self._build_bid_response(bid))
            
            return bid_responses
            
        except Exception as e:
            logger.error(f"Error bulk updating bid status: {e}")
            return []

    def bulk_delete_bids(self, db: Session, bid_ids: List[UUID],
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk delete bids with permission checks."""
        try:
            return self.bid_repo.bulk_delete(
                db, bid_ids, requesting_user_id, requesting_user_role, requesting_user_team_id
            )
        except Exception as e:
            logger.error(f"Error bulk deleting bids: {e}")
            return BulkOperationResult(
                success_count=0, failed_count=len(bid_ids), total_count=len(bid_ids), errors=[str(e)]
            )

    def bulk_assign_team(self, db: Session, bid_ids: List[UUID], target_team_id: UUID,
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None) -> BulkOperationResult:
        """Bulk assign bids to team (admin only)."""
        try:
            return self.bid_repo.bulk_assign_team(
                db, bid_ids, target_team_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            )
        except Exception as e:
            logger.error(f"Error bulk assigning team: {e}")
            return BulkOperationResult(
                success_count=0, failed_count=len(bid_ids), total_count=len(bid_ids), errors=[str(e)]
            )

    def get_recent_bids(self, db: Session,
                       requesting_user_id: UUID, requesting_user_role: UserRole, limit: int = 10,
                       requesting_user_team_id: Optional[UUID] = None) -> List[BidResponse]:
        """Get recent bids with role-based filtering."""
        try:
            team_id = None
            member_id = None
            
            # Apply role-based filtering
            if requesting_user_role == UserRole.MEMBER:
                member_id = requesting_user_id
            elif requesting_user_role == UserRole.SUB_ADMIN:
                team_id = requesting_user_team_id
            
            bids = self.bid_repo.get_recent_bids(db, limit, team_id, member_id)
            return [self._build_bid_response(bid) for bid in bids]
            
        except Exception as e:
            logger.error(f"Error getting recent bids: {e}")
            return []

    def get_winning_bids(self, db: Session, 
                        requesting_user_id: UUID, requesting_user_role: UserRole,skip: int = 0, limit: int = 20,
                        requesting_user_team_id: Optional[UUID] = None) -> PaginatedResponse[BidResponse]:
        """Get winning bids with role-based filtering."""
        try:
            team_id = None
            member_id = None
            
            # Apply role-based filtering
            if requesting_user_role == UserRole.MEMBER:
                member_id = requesting_user_id
            elif requesting_user_role == UserRole.SUB_ADMIN:
                team_id = requesting_user_team_id
            
            result = self.bid_repo.get_winning_bids(db, team_id, member_id, skip, limit)
            bid_responses = [self._build_bid_response(bid) for bid in result.items]
            
            return PaginatedResponse(
                items=bid_responses,
                next_cursor=result.next_cursor,
                count=result.count
            )
            
        except Exception as e:
            logger.error(f"Error getting winning bids: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_my_bids(self, db: Session, filters: BidListFilter,
                   requesting_user_id: UUID, skip: int = 0, limit: int = 20,
                   sort_by: str = "-submitted_at") -> PaginatedResponse[BidResponse]:
        """Get current user's bids (convenience method for members)."""
        try:
            filters.member_id = requesting_user_id
            
            result = self.bid_repo.get_all(db, filters, skip, limit, sort_by)
            bid_responses = [self._build_bid_response(bid) for bid in result.items]
            
            return PaginatedResponse(
                items=bid_responses,
                next_cursor=result.next_cursor,
                count=result.count
            )
            
        except Exception as e:
            logger.error(f"Error getting my bids: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_dashboard_summary(self, db: Session, requesting_user_id: UUID,
                             requesting_user_role: UserRole,
                             requesting_user_team_id: Optional[UUID] = None) -> DashboardSummary:
        """Get bid summary for dashboard display based on user role."""
        try:
            team_id = None
            member_id = None
            
            if requesting_user_role == UserRole.MEMBER:
                member_id = requesting_user_id
            elif requesting_user_role == UserRole.SUB_ADMIN:
                team_id = requesting_user_team_id
            
            stats = self.get_bid_statistics(
                db, team_id, member_id, None, requesting_user_role, requesting_user_team_id
            )
            
            recent_bids = self.get_recent_bids(
                db, 5, requesting_user_id, requesting_user_role, requesting_user_team_id
            )
            
            # Get top performers (admin and sub-admin only)
            top_performers = []
            if requesting_user_role in [UserRole.ADMIN, UserRole.SUB_ADMIN]:
                top_performers = self.get_top_performers(
                    db, team_id, 5, requesting_user_role, requesting_user_team_id
                )
            
            # Get team performance (sub-admin and admin only)
            team_performance = None
            if requesting_user_role in [UserRole.ADMIN, UserRole.SUB_ADMIN] and team_id:
                team_stats = self.get_team_statistics(
                    db, team_id, requesting_user_role, requesting_user_team_id
                )
                if team_stats:
                    team_performance = team_stats[0]
            
            # Get earnings this month
            current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            earnings_response = self.get_earnings(
                db, team_id, member_id, None, requesting_user_role, 
                requesting_user_team_id, current_month_start
            )
            
            # Get pending bids count
            pending_bids = self.get_pending_bids_count(
                db, requesting_user_id, requesting_user_role, requesting_user_team_id
            )
            
            # Convert recent bids to BidSummary
            bid_summaries = []
            for bid_response in recent_bids:
                bid_summaries.append(BidSummary(
                    id=bid_response.id,
                    job_title=bid_response.job_title,
                    status=bid_response.status,
                    budget_type=bid_response.budget_type,
                    connects_used=bid_response.connects_used,
                    total_cost=bid_response.total_cost,
                    submitted_at=bid_response.submitted_at,
                    member_name="Current User",  # Would need to fetch actual name
                    vertical_name="Vertical"  # Would need to fetch actual vertical name
                ))
            
            return DashboardSummary(
                statistics=stats,
                recent_bids=bid_summaries,
                top_performers=top_performers,
                team_performance=team_performance,
                earnings_this_month=earnings_response.total_earnings,
                pending_bids=pending_bids
            )
            
        except Exception as e:
            logger.error(f"Error getting dashboard summary: {e}")
            return DashboardSummary(
                statistics=BidStats(total_bids=0, wins=0, win_rate=0, total_connects_used=0, total_cost=0),
                recent_bids=[]
            )

    def get_top_performers(self, db: Session, team_id: Optional[UUID] = None,
                          limit: int = 5, requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None) -> List[MemberBidRanking]:
        """Get top performing members with role-based access."""
        try:
            if requesting_user_role == UserRole.MEMBER:
                return []  # Members cannot see rankings
            
            return self.bid_repo.get_top_performers(db, team_id, limit)
        except Exception as e:
            logger.error(f"Error getting top performers: {e}")
            return []

    def get_monthly_trends(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None, months: int = 12,
                          requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None) -> List[MonthlyTrend]:
        """Get monthly bid trends with role-based access."""
        try:
            # Apply role-based filtering
            if requesting_user_role == UserRole.MEMBER and member_id:
                pass  # member_id already set
            elif requesting_user_role == UserRole.SUB_ADMIN:
                team_id = requesting_user_team_id
                if member_id:
                    member = self.user_repo.get_by_id(db, member_id)
                    if not member or member.team_id != requesting_user_team_id:
                        member_id = None
            
            return self.bid_repo.get_monthly_trends(db, team_id, member_id, months)
        except Exception as e:
            logger.error(f"Error getting monthly trends: {e}")
            return []

    def get_pending_bids_count(self, db: Session, requesting_user_id: UUID,
                              requesting_user_role: UserRole,
                              requesting_user_team_id: Optional[UUID] = None) -> int:
        """Get count of pending bids based on user role."""
        try:
            team_id = None
            member_id = None
            
            if requesting_user_role == UserRole.MEMBER:
                member_id = requesting_user_id
            elif requesting_user_role == UserRole.SUB_ADMIN:
                team_id = requesting_user_team_id
            
            pending_bids = self.bid_repo.get_pending_bids(db, team_id, member_id)
            return len(pending_bids)
        except Exception as e:
            logger.error(f"Error getting pending bids count: {e}")
            return 0

    def calculate_bid_costs(self, connects_used: int, boost_connects: int = 0) -> dict:
        """Calculate bid costs (connect cost, total cost)."""
        try:
            connect_cost = calculate_connect_cost(connects_used, boost_connects)
            
            return {
                "connects_used": connects_used,
                "boost_connects_used": boost_connects,
                "connect_cost": float(connect_cost),
                "total_cost": float(connect_cost)
            }
        except Exception as e:
            logger.error(f"Error calculating bid costs: {e}")
            return {}

    def check_bid_edit_permission(self, db: Session, bid_id: UUID,
                                 requesting_user_id: UUID, requesting_user_role: UserRole) -> dict:
        """Check if current user can edit the specified bid with detailed response."""
        try:
            can_edit = self.validate_bid_edit_permission(db, bid_id, requesting_user_id, requesting_user_role)
            
            bid = self.bid_repo.get_by_id(db, bid_id)
            days_remaining = None
            
            if bid and requesting_user_role == UserRole.MEMBER:
                days_since = calculate_days_since(bid.created_at)
                days_remaining = max(0, 5 - days_since)
            
            return {
                "bid_id": str(bid_id),
                "can_edit": can_edit,
                "reason": "Within edit window" if can_edit else "Edit window expired or insufficient permissions",
                "days_remaining": days_remaining
            }
            
        except Exception as e:
            logger.error(f"Error checking bid edit permission: {e}")
            return {
                "bid_id": str(bid_id),
                "can_edit": False,
                "reason": "Error checking permissions"
            }

    def create_bid_notification(self, db: Session, bid_id: UUID, 
                               old_status: Optional[BidStatus] = None,
                               new_status: Optional[BidStatus] = None) -> None:
        """Create notifications for bid status changes."""
        try:
            self.notification_repo.create_bid_notification(db, bid_id, "status_changed")
        except Exception as e:
            logger.error(f"Error creating bid notification: {e}")

    def auto_create_receivable(self, db: Session, bid_id: UUID) -> None:
        """Automatically create receivable for won bids."""
        try:
            logger.info(f"Auto-creating receivable for won bid {bid_id}")
            # Implementation would call receivable service
        except Exception as e:
            logger.error(f"Error auto-creating receivable: {e}")

    # Private helper methods
    def _build_bid_response(self, bid) -> BidResponse:
        """Build bid response with derived fields."""
        try:
            estimated_value = estimate_project_value(
                bid.budget_type.value, bid.budget_min, bid.budget_max,
                bid.hourly_rate, bid.estimated_hours
            )
            
            days_since_submission = calculate_days_since(bid.submitted_at)
            can_edit = can_edit_bid(bid.created_at)
            
            # Create BidDerived object
            derived = BidDerived(
                estimated_value=estimated_value,
                days_since_submission=days_since_submission,
                can_edit=can_edit
            )
            
            # Create clean response data
            response_data = {
                'id': bid.id,
                'job_title': bid.job_title,
                'job_url': str(bid.job_url) if bid.job_url else None,
                'job_description': bid.job_description,
                'client_name': bid.client_name,
                'budget_type': bid.budget_type,
                'budget_min': bid.budget_min,
                'budget_max': bid.budget_max,
                'hourly_rate': bid.hourly_rate,
                'estimated_hours': bid.estimated_hours,
                'connects_used': bid.connects_used,
                'boost_connects_used': bid.boost_connects_used,
                'proposal_text': bid.proposal_text,
                'cover_letter': bid.cover_letter,
                'is_featured': bid.is_featured,
                'competition_level': bid.competition_level,
                'notes': bid.notes,
                'vertical_id': bid.vertical_id,
                'member_id': bid.member_id,
                'team_id': bid.team_id,
                'connect_cost': bid.connect_cost,
                'total_cost': bid.total_cost,
                'status': bid.status,
                'submitted_at': bid.submitted_at,
                'last_status_change': bid.last_status_change,
                'created_at': bid.created_at,
                'updated_at': bid.updated_at,
                'derived': derived
            }
            
            return BidResponse(**response_data)
            
        except Exception as e:
            logger.error(f"Error building bid response: {e}")
            raise

    def _apply_role_based_filters(self, filters: BidListFilter, role: UserRole,
                                 user_id: UUID, team_id: Optional[UUID]) -> BidListFilter:
        """Apply role-based filters to bid queries."""
        if role == UserRole.MEMBER:
            filters.member_id = user_id
        elif role == UserRole.SUB_ADMIN:
            filters.team_id = team_id
        
        return filters

    def _validate_bid_creation_permission(self, db: Session, bid_data: BidCreate,
                                        requesting_user_id: UUID, requesting_user_role: UserRole,
                                        requesting_user_team_id: Optional[UUID]) -> bool:
        """Validate bid creation permissions."""
        # Admin can create bids for any team
        if requesting_user_role == UserRole.ADMIN:
            return True
        
        # Validate that user belongs to the specified team
        user = self.user_repo.get_by_id(db, requesting_user_id)
        if not user or not user.is_active:
            return False
        
        # Check if user is a member of the specified team
        is_team_member = self.team_repo.get_by_id(db, bid_data.team_id)
        if not is_team_member:
            return False
        
        return True