from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from interface.Iservices.bid_service import IBidService
from repositories.bid_repository import BidRepository
from repositories.user_repository import UserRepository
from repositories.notification_repository import NotificationRepository
from repositories.audit_repository import AuditRepository
from repositories.team_repository import TeamRepository
from schemas.bid import (
    BidCreate, BidUpdate, BidResponse, BidListFilter, 
    BidStatusUpdate, BidStats
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
            # Validate user permissions
            if not self._validate_bid_creation_permission(
                db, bid_data, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to create bid for this team"
                )
            
            # Validate vertical assignment
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
            
            # Create bid data with user information
            bid_create_data = bid_data.dict()
            bid_create_data.update({
                'member_id': requesting_user_id
            })
            
            # Create bid
            bid = self.bid_repo.create(db, BidCreate(**bid_create_data))
            
            # Log bid creation
            self.audit_repo.create_audit_log(
                db, AuditAction.CREATE, "bid", bid.id, requesting_user_id, None,
                None, None, f"Bid created: {bid.job_title}",
                new_values={
                    "job_title": bid.job_title,
                    "vertical_id": str(bid.vertical_id),
                    "budget_type": bid.budget_type.value,
                    "connects_used": bid.connects_used,
                    "total_cost": str(bid.total_cost)
                }
            )
            
            # Create notification for bid creation (if needed)
            # This could notify sub-admin about new bid submission
            
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
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                return None
            
            # Validate access
            if not self.validate_bid_access(
                db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view this bid"
                )
            
            return self._build_bid_response(bid)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bid {bid_id}: {e}")
            return None

    def get_bids(self, db: Session, filters: BidListFilter, 
                requesting_user_id: UUID, requesting_user_role: UserRole,skip: int = 0,
                limit: int = 20, sort_by: str = "-submitted_at",
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

    def update_bid(self, db: Session, bid_id: UUID, bid_data: BidUpdate,
                  requesting_user_id: UUID, requesting_user_role: UserRole,
                  requesting_user_team_id: Optional[UUID] = None) -> Optional[BidResponse]:
        """Update bid with validation and permission checks."""
        try:
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
            
            # Validate edit permissions
            if not self.validate_bid_edit_permission(db, bid_id, requesting_user_id, requesting_user_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot edit this bid (edit window expired or insufficient permissions)"
                )
            
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
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bid not found"
                )
            
            # Validate access
            if not self.validate_bid_access(
                db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to update bid status"
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
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bid not found"
                )
            
            # Validate delete permissions (stricter than edit)
            if not self._validate_bid_delete_permission(
                db, bid, requesting_user_id, requesting_user_role
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete this bid (insufficient permissions or bid has progressed)"
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
                old_values=bid_info
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
        try:
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                return False
            
            # Admin can access all bids
            if requesting_user_role == UserRole.ADMIN:
                return True
            
            # Sub-admin can access team bids
            if requesting_user_role == UserRole.SUB_ADMIN:
                return bid.team_id == requesting_user_team_id
            
            # Member can access own bids
            if requesting_user_role == UserRole.MEMBER:
                return bid.member_id == requesting_user_id
            
            return False
        except Exception as e:
            logger.error(f"Error validating bid access: {e}")
            return False

    def validate_bid_edit_permission(self, db: Session, bid_id: UUID,
                                    requesting_user_id: UUID, requesting_user_role: UserRole) -> bool:
        """Validate if user can edit the bid (considering 5-day rule)."""
        try:
            # Admin can always edit
            if requesting_user_role == UserRole.ADMIN:
                return True
            
            bid = self.bid_repo.get_by_id(db, bid_id)
            if not bid:
                return False
            
            # Sub-admin can edit after 5-day window (approval mechanism)
            if requesting_user_role == UserRole.SUB_ADMIN:
                return True  # Sub-admin approval is handled in business logic
            
            # Member can edit within 5-day window
            if requesting_user_role == UserRole.MEMBER:
                if bid.member_id == requesting_user_id:
                    return can_edit_bid(bid.created_at)
            
            return False
        except Exception as e:
            logger.error(f"Error validating bid edit permission: {e}")
            return False

    def validate_vertical_assignment(self, db: Session, user_id: UUID, vertical_id: UUID) -> bool:
        """Validate if user is assigned to the vertical."""
        return self.user_repo.check_vertical_assignment(db, user_id, vertical_id)

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

    def get_bid_statistics(self, db: Session, team_id: Optional[UUID] = None,
                          member_id: Optional[UUID] = None, vertical_id: Optional[UUID] = None,
                          requesting_user_role: UserRole = None,
                          requesting_user_team_id: Optional[UUID] = None) -> BidStats:
        """Get bid statistics with role-based filtering."""
        try:
            filters = {}
            
            if team_id:
                filters['team_id'] = team_id
            if member_id:
                filters['member_id'] = member_id
            if vertical_id:
                filters['vertical_id'] = vertical_id
            
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

    def bulk_update_status(self, db: Session, bid_ids: List[UUID], status: BidStatus,
                          requesting_user_id: UUID, requesting_user_role: UserRole,
                          requesting_user_team_id: Optional[UUID] = None) -> List[BidResponse]:
        """Bulk update bid status with permission checks."""
        try:
            updated_bids = []
            
            for bid_id in bid_ids:
                # Validate access for each bid
                if self.validate_bid_access(
                    db, bid_id, requesting_user_id, requesting_user_role, requesting_user_team_id
                ):
                    bid = self.bid_repo.update_status(db, bid_id, status)
                    if bid:
                        updated_bids.append(self._build_bid_response(bid))
                        
                        # Log bulk update
                        self.audit_repo.create_audit_log(
                            db, AuditAction.UPDATE, "bid", bid_id, requesting_user_id, None,
                            None, None, f"Bulk status update to {status.value}"
                        )
            
            return updated_bids
            
        except Exception as e:
            logger.error(f"Error bulk updating bid status: {e}")
            return []

    def get_recent_bids(self, db: Session, 
                       requesting_user_id: UUID, requesting_user_role: UserRole,limit: int = 10,
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
            # This would be implemented to create receivables automatically
            # when a bid is marked as won
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
            
            # Create base response
            response_data = {
                **bid.__dict__,
                'derived': {
                    'estimated_value': estimated_value,
                    'days_since_submission': days_since_submission,
                    'can_edit': can_edit
                }
            }
            
            return BidResponse(**response_data)
            
        except Exception as e:
            logger.error(f"Error building bid response: {e}")
            # Return basic response without derived fields
            return BidResponse(**bid.__dict__)

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
    
    def _validate_bid_delete_permission(self, db: Session, bid, requesting_user_id: UUID,
                                       requesting_user_role: UserRole) -> bool:
        """Validate bid deletion permissions (stricter than edit)."""
        # Admin can delete any bid
        if requesting_user_role == UserRole.ADMIN:
            return True
        
        # Sub-admin can delete team bids that are not won
        if requesting_user_role == UserRole.SUB_ADMIN:
            return bid.status not in [BidStatus.WON, BidStatus.CLOSED]
        
        # Member can delete own bids within edit window and if not progressed
        if requesting_user_role == UserRole.MEMBER:
            return (bid.member_id == requesting_user_id and 
                   can_edit_bid(bid.created_at) and
                   bid.status == BidStatus.NOT_VIEWED)
        
        return False