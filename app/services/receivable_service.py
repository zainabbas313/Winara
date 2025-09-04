from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import date, datetime
from fastapi import HTTPException, status
from models.models import Receivable, Bid, BidStatus, UserRole, ReceivableStatus, ProjectModule, PaymentType, ModuleStatus
from schemas.receivable import (
    ReceivableCreate, ReceivableUpdate, ReceivableResponse, ReceivableListFilter,
    ReceivableStatusUpdate, ReceivableStats, ReceivableDerived, BulkReceivableCreate,
    BidReceivableResponse, ProjectModuleResponse
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
            
            # Validate team access
            if user_role == UserRole.SUB_ADMIN.value:
                if bid.team_id != user_team_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Can only create receivables for your own team's bids"
                    )
            
            # Validate module if module-based payment
            if receivable_data.payment_type == PaymentType.MODULE_BASED:
                if not receivable_data.module_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Module ID is required for module-based payments"
                    )
                
                module = db.query(ProjectModule).filter(
                    ProjectModule.id == receivable_data.module_id,
                    ProjectModule.bid_id == receivable_data.bid_id
                ).first()
                
                if not module:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Module not found or doesn't belong to this bid"
                    )
                
                # Check if receivable already exists for this module
                existing_receivable = self.repository.get_by_module(db, receivable_data.module_id)
                if existing_receivable:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Receivable already exists for this module"
                    )
            
            else:  # Single payment
                # Check if any receivable already exists for this bid
                existing_receivables = self.repository.get_by_bid(db, receivable_data.bid_id)
                if existing_receivables:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Receivable already exists for this bid"
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
    
    def create_bulk_receivables(self, db: Session, bulk_data: BulkReceivableCreate,
                               created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> List[ReceivableResponse]:
        """Create receivables for all modules of a bid."""
        try:
            # Validate bid exists and is won
            bid = db.query(Bid).filter(Bid.id == bulk_data.bid_id).first()
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
            
            # Validate team access
            if user_role == UserRole.SUB_ADMIN.value:
                if bid.team_id != user_team_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Can only create receivables for your own team's bids"
                    )
            
            # Check if any receivables already exist for this bid
            existing_receivables = self.repository.get_by_bid(db, bulk_data.bid_id)
            if existing_receivables:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Receivables already exist for this bid"
                )
            
            # Create modules and receivables
            receivables = self.repository.create_bulk_modules_and_receivables(
                db, bulk_data.bid_id, bulk_data.modules, created_by_id, bulk_data.currency
            )
            
            return [self._to_response(receivable) for receivable in receivables]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating bulk receivables: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while creating bulk receivables"
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
    
    def get_bid_receivables(self, db: Session, bid_id: UUID, user_id: UUID, user_role: str,
                           user_team_id: Optional[UUID] = None) -> BidReceivableResponse:
        """Get all receivables for a specific bid."""
        try:
            # Get bid with access control
            bid = db.query(Bid).filter(Bid.id == bid_id).first()
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bid not found"
                )
            
            # Check access
            if user_role == UserRole.SUB_ADMIN.value:
                if bid.team_id != user_team_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this bid"
                    )
            
            # Get receivables
            receivables = self.repository.get_by_bid(db, bid_id)
            
            # Get modules if they exist
            modules = db.query(ProjectModule).filter(ProjectModule.bid_id == bid_id).all()
            
            # Calculate total contract value
            total_contract_value = sum(r.contract_value for r in receivables)
            
            return BidReceivableResponse(
                bid_id=bid.id,
                job_title=bid.job_title,
                client_name=str(bid.client_name),
                has_modules=bid.has_modules,
                total_contract_value=total_contract_value,
                receivables=[self._to_response(r) for r in receivables],
                modules=[self._module_to_response(m) for m in modules]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bid receivables: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while getting bid receivables"
            )
    
    def get_receivables(self, db: Session, filters: ReceivableListFilter, user_id: UUID, user_role: str, 
                       skip: int = 0, limit: int = 20, sort_by: str = "-created_at",
                       user_team_id: Optional[UUID] = None) -> PaginatedResponse[ReceivableResponse]:
        """Get receivables with filtering, pagination and access control."""
        # Apply access control to filters
        if user_role == UserRole.SUB_ADMIN.value:
            filters.team_id = user_team_id
        
        result = self.repository.get_all(db, filters, skip, limit, sort_by)
        
        # Convert items to response format
        response_items = [self._to_response(item) for item in result.items]
        
        return PaginatedResponse(
            items=response_items,
            next_cursor=result.next_cursor,
            count=result.count
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
                total_receivables=stats_data.get('total_receivables', 0),
                total_value=stats_data.get('total_value', 0),
                paid_value=stats_data.get('paid_value', 0),
                pending_value=stats_data.get('pending_value', 0),
                partial_value=stats_data.get('partial_value', 0),
                overdue_value=stats_data.get('overdue_value', 0),
                overdue_count=stats_data.get('overdue_count', 0),
                avg_payment_days=stats_data.get('avg_payment_days'),
                collection_rate=stats_data.get('collection_rate', 0),
                by_status=stats_data.get('by_status', []),
                by_payment_type=stats_data.get('by_payment_type', []),
                by_currency=stats_data.get('by_currency', []),
                current_month_value=stats_data.get('current_month_value', 0),
                next_month_value=stats_data.get('next_month_value', 0)
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
            return receivable.bid.team_id == user_team_id
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
    
    def _module_to_response(self, module: ProjectModule) -> ProjectModuleResponse:
        """Convert ProjectModule to response format."""
        return ProjectModuleResponse(
            id=module.id,
            bid_id=module.bid_id,
            module_name=module.module_name,
            description=module.description,
            module_amount=module.module_amount,
            order_sequence=module.order_sequence,
            status=module.status,
            created_at=module.created_at,
            updated_at=module.updated_at
        )
    
    def _to_response(self, receivable: Receivable) -> ReceivableResponse:
        """Convert Receivable model to ReceivableResponse schema."""
        derived = self._calculate_derived_fields(receivable)
        
        # Get client name and project title
        client_name = receivable.bid.client_name if receivable.bid else None
        
        if receivable.module:
            project_title = f"{receivable.bid.job_title} - {receivable.module.module_name}"
            module_response = self._module_to_response(receivable.module)
        else:
            project_title = receivable.bid.job_title if receivable.bid else None
            module_response = None
        
        return ReceivableResponse(
            id=receivable.id,
            bid_id=receivable.bid_id,
            module_id=receivable.module_id,
            contract_value=receivable.contract_value,
            expected_payment_date=receivable.expected_payment_date,
            actual_payment_date=receivable.actual_payment_date,
            payment_amount=receivable.payment_amount,
            status=receivable.status,
            payment_type=receivable.payment_type,
            currency=receivable.currency,
            created_at=receivable.created_at,
            updated_at=receivable.updated_at,
            created_by_id=receivable.created_by_id,
            derived=derived,
            module=module_response,
            client_name=str(client_name),
            project_title=project_title
        )