from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import date, datetime
from fastapi import HTTPException, status
from models.models import Receivable, Bid, BidStatus, UserRole, ReceivableStatus
from schemas.receivable import (
    ReceivableCreate, ReceivableUpdate, ReceivableResponse, ReceivableListFilter,
    ReceivableStatusUpdate, ReceivableStats, ReceivableDerived
)
from schemas.common import SuccessResponse, PaginatedResponse
from repositories.receivable_repository import ReceivableRepository
from interface.Iservices.receivable_service import IReceivableService
import logging

logger = logging.getLogger(__name__)


class ReceivableService(IReceivableService):
    
    def __init__(self):
        self.repository = ReceivableRepository()
    
    def create_receivable(self, db: Session, receivable_data: ReceivableCreate, 
                         created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> ReceivableResponse:
        """Create a new receivable."""
        try:
            # Validate bid exists and is won
            bid = db.query(Bid).filter(Bid.id == receivable_data.bid_id).first()
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bid not found"
                )
            
            if bid.status != BidStatus.WON:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only create receivables for won bids"
                )
            
            # Check if receivable already exists for this bid
            existing_receivable = self.repository.get_by_bid(db, receivable_data.bid_id)
            if existing_receivable:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Receivable already exists for this bid"
                )
            
            # Validate team access
            if user_role == UserRole.SUB_ADMIN.value:
                if receivable_data.team_id != user_team_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Can only create receivables for your own team"
                    )
            
            receivable = self.repository.create(db, receivable_data, created_by_id)
            return self._to_response(receivable)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating receivable: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while creating receivable"
            )
    
    def get_receivable(self, db: Session, receivable_id: UUID, user_id: UUID,
                      user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        """Get receivable by ID with access control."""
        receivable = self.repository.get_by_id(db, receivable_id)
        if not receivable:
            return None
        
        # Access control
        if not self._has_access_to_receivable(receivable, user_role, user_team_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this receivable"
            )
        
        return self._to_response(receivable)
    
    def get_receivables(self, db: Session, filters: ReceivableListFilter,  user_id: UUID, user_role: str, skip: int = 0,
                       limit: int = 20, sort_by: str = "-created_at",
                        user_team_id: Optional[UUID] = None) -> PaginatedResponse[ReceivableResponse]:
        """Get receivables with filtering, pagination and access control."""
        # Apply access control to filters
        if user_role == UserRole.SUB_ADMIN.value:
            filters.team_id = user_team_id
        
        result = self.repository.get_all(db, filters, skip, limit, sort_by)
        
        return PaginatedResponse(
            items=[self._to_response(item) for item in result.items],
            total=result.total,
            skip=result.skip,
            limit=result.limit,
            has_next=result.has_next,
            has_prev=result.has_prev
        )
    
    def update_receivable(self, db: Session, receivable_id: UUID, receivable_data: ReceivableUpdate,
                         user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        """Update receivable with access control."""
        try:
            receivable = self.repository.get_by_id(db, receivable_id)
            if not receivable:
                return None
            
            # Access control
            if not self._has_access_to_receivable(receivable, user_role, user_team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this receivable"
                )
            
            # Validate status transitions if status is being updated
            if receivable_data.status and not self._is_valid_status_transition(receivable.status, receivable_data.status):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status transition from {receivable.status.value} to {receivable_data.status.value}"
                )
            
            # Validate payment data consistency
            if receivable_data.status in [ReceivableStatus.PAID, ReceivableStatus.PARTIAL]:
                if not receivable_data.payment_amount and receivable_data.status == ReceivableStatus.PAID:
                    # Default to contract value if not specified
                    receivable_data.payment_amount = receivable.contract_value
                
                if not receivable_data.actual_payment_date and receivable_data.status == ReceivableStatus.PAID:
                    receivable_data.actual_payment_date = date.today()
            
            updated_receivable = self.repository.update(db, receivable_id, receivable_data)
            return self._to_response(updated_receivable) if updated_receivable else None
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating receivable {receivable_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating receivable"
            )
    
    def update_receivable_status(self, db: Session, receivable_id: UUID, status_data: ReceivableStatusUpdate,
                                user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ReceivableResponse]:
        """Update receivable status with access control."""
        try:
            receivable = self.repository.get_by_id(db, receivable_id)
            if not receivable:
                return None
            
            # Access control
            if not self._has_access_to_receivable(receivable, user_role, user_team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this receivable"
                )
            
            # Validate status transition
            if not self._is_valid_status_transition(receivable.status, status_data.status):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status transition from {receivable.status.value} to {status_data.status.value}"
                )
            
            # Update receivable with status and payment data
            update_data = ReceivableUpdate(
                status=status_data.status,
                actual_payment_date=status_data.actual_payment_date,
                payment_amount=status_data.payment_amount
            )
            
            updated_receivable = self.repository.update(db, receivable_id, update_data)
            return self._to_response(updated_receivable) if updated_receivable else None
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating receivable status {receivable_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating receivable status"
            )
    
    def delete_receivable(self, db: Session, receivable_id: UUID, user_id: UUID,
                         user_role: str, user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Delete receivable with access control."""
        try:
            receivable = self.repository.get_by_id(db, receivable_id)
            if not receivable:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Receivable not found"
                )
            
            # Access control
            if not self._has_access_to_receivable(receivable, user_role, user_team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this receivable"
                )
            
            success = self.repository.delete(db, receivable_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Receivable not found"
                )
            
            return SuccessResponse(message="Receivable deleted successfully")
            
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error deleting receivable {receivable_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while deleting receivable"
            )
    
    def get_overdue_receivables(self, db: Session, team_id: Optional[UUID] = None) -> List[ReceivableResponse]:
        """Get overdue receivables."""
        receivables = self.repository.get_overdue(db, team_id)
        return [self._to_response(receivable) for receivable in receivables]
    
    def get_statistics(self, db: Session, team_id: Optional[UUID] = None) -> ReceivableStats:
        """Get receivable statistics."""
        try:
            stats_data = self.repository.get_statistics(db, team_id)
            
            return ReceivableStats(
                total_receivables=stats_data['total_receivables'],
                total_value=stats_data['total_value'],
                paid_value=stats_data['paid_value'],
                pending_value=stats_data['pending_value'],
                partial_value=stats_data['partial_value'],
                overdue_value=stats_data['overdue_value'],
                overdue_count=stats_data['overdue_count'],
                avg_payment_days=stats_data['avg_payment_days'],
                collection_rate=stats_data['collection_rate'],
                by_status=stats_data['by_status'],
                by_currency=stats_data['by_currency'],
                current_month_value=stats_data['current_month_value'],
                next_month_value=stats_data['next_month_value']
            )
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while getting statistics"
            )
    
    def get_monthly_summary(self, db: Session, year: int, month: int, 
                           team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get monthly receivables summary."""
        try:
            return self.repository.get_monthly_summary(db, year, month, team_id)
        except Exception as e:
            logger.error(f"Error getting monthly summary: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while getting monthly summary"
            )
    
    def get_payment_trends(self, db: Session, team_id: Optional[UUID] = None,
                          days: int = 90) -> List[Dict[str, Any]]:
        """Get payment trends over specified period."""
        try:
            return self.repository.get_payment_trends(db, team_id, days)
        except Exception as e:
            logger.error(f"Error getting payment trends: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while getting payment trends"
            )
    
    def get_client_summary(self, db: Session, team_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Get summary statistics by client."""
        try:
            return self.repository.get_client_summary(db, team_id)
        except Exception as e:
            logger.error(f"Error getting client summary: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while getting client summary"
            )
    
    def calculate_cash_flow(self, db: Session, team_id: Optional[UUID] = None,
                           days_ahead: int = 90) -> List[Dict[str, Any]]:
        """Calculate projected cash flow based on expected payment dates."""
        try:
            return self.repository.calculate_cash_flow(db, team_id, days_ahead)
        except Exception as e:
            logger.error(f"Error calculating cash flow: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while calculating cash flow"
            )
    
    def mark_overdue_receivables(self, db: Session) -> int:
        """Mark overdue receivables and return count."""
        try:
            return self.repository.mark_overdue(db)
        except Exception as e:
            logger.error(f"Error marking overdue receivables: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while marking overdue receivables"
            )
    
    def _has_access_to_receivable(self, receivable: Receivable, user_role: str, user_team_id: Optional[UUID]) -> bool:
        """Check if user has access to the receivable."""
        if user_role == UserRole.ADMIN.value:
            return True
        elif user_role == UserRole.SUB_ADMIN.value:
            return receivable.team_id == user_team_id
        else:
            return False  # Members don't have access to receivables
    
    def _is_valid_status_transition(self, current_status: ReceivableStatus, new_status: ReceivableStatus) -> bool:
        """Validate status transitions."""
        valid_transitions = {
            ReceivableStatus.PENDING: [ReceivableStatus.PARTIAL, ReceivableStatus.PAID, ReceivableStatus.OVERDUE],
            ReceivableStatus.PARTIAL: [ReceivableStatus.PAID, ReceivableStatus.OVERDUE],
            ReceivableStatus.OVERDUE: [ReceivableStatus.PAID, ReceivableStatus.PARTIAL],
            ReceivableStatus.PAID: []  # No transitions from paid
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    def _calculate_derived_fields(self, receivable: Receivable) -> ReceivableDerived:
        """Calculate derived fields for a receivable."""
        today = date.today()
        expected_date = receivable.expected_payment_date
        
        # Calculate overdue status
        is_overdue = (
            expected_date < today and 
            receivable.status in [ReceivableStatus.PENDING, ReceivableStatus.PARTIAL]
        )
        
        # Calculate days overdue
        if is_overdue:
            days_overdue = (today - expected_date).days
        else:
            days_overdue = 0
        
        # Calculate days until due
        days_until_due = (expected_date - today).days
        
        # Calculate payment delay
        payment_delay = None
        if receivable.actual_payment_date and receivable.status == ReceivableStatus.PAID:
            payment_delay = (receivable.actual_payment_date - expected_date).days
        
        return ReceivableDerived(
            is_overdue=is_overdue,
            days_overdue=days_overdue,
            days_until_due=days_until_due,
            payment_delay=payment_delay
        )
    
    def _to_response(self, receivable: Receivable) -> ReceivableResponse:
        """Convert Receivable model to ReceivableResponse schema."""
        derived = self._calculate_derived_fields(receivable)
        
        return ReceivableResponse(
            id=receivable.id,
            bid_id=receivable.bid_id,
            team_id=receivable.team_id,
            client_name=receivable.client_name,
            project_title=receivable.project_title,
            contract_value=receivable.contract_value,
            expected_payment_date=receivable.expected_payment_date,
            actual_payment_date=receivable.actual_payment_date,
            payment_amount=receivable.payment_amount,
            status=receivable.status,
            currency=receivable.currency,
            created_at=receivable.created_at,
            updated_at=receivable.updated_at,
            created_by_id=receivable.created_by_id,
            derived=derived
        )