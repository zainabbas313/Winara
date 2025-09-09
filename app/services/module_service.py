from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models.models import ProjectModule, Bid, BidStatus, UserRole, Receivable, ModuleStatus
from schemas.module import (
    ModuleCreate, ModuleUpdate, ModuleResponse, ModuleListFilter,
    ModuleBulkCreate, ModuleStatusUpdate, BidModulesResponse, BidStatusCheck
)
from schemas.common import SuccessResponse, PaginatedResponse
from repositories.module_repository import ModuleRepository
from interface.Iservices.module_service import IModuleService
import logging

logger = logging.getLogger(__name__)


class ModuleService(IModuleService):
    
    def __init__(self):
        self.repository = ModuleRepository()
    
    def create_module(self, db: Session, module_data: ModuleCreate, 
                     created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> ModuleResponse:
        """Create a new project module."""
        try:
            # Validate bid exists and is won
            bid = db.query(Bid).filter(Bid.id == module_data.bid_id).first()
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bid not found"
                )
            
            if bid.status != BidStatus.WON:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only create modules for won bids"
                )
            
            # Validate team access
            if user_role == UserRole.SUB_ADMIN.value:
                if bid.team_id != user_team_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Can only create modules for your own team's bids"
                    )
            
            # Check if receivables already exist for this bid
            existing_receivables = db.query(Receivable).filter(Receivable.bid_id == module_data.bid_id).first()
            if existing_receivables:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create modules: Receivables already exist for this bid. Use PUT API to update existing modules or DELETE receivables first."
                )
            
            # Check for duplicate order sequence in existing modules
            existing_module_with_sequence = db.query(ProjectModule).filter(
                ProjectModule.bid_id == module_data.bid_id,
                ProjectModule.order_sequence == module_data.order_sequence
            ).first()
            
            if existing_module_with_sequence:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Module with order sequence {module_data.order_sequence} already exists for this bid"
                )
            
            module = self.repository.create(db, module_data)
            return self._to_response(db, module)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating module: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while creating module"
            )
    
    def create_single_module(self, db: Session, module_data: ModuleCreate, 
                            created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> ModuleResponse:
        """Create a single module for a bid - Single Module Workflow."""
        try:
            # Validate bid exists and is won
            bid = db.query(Bid).filter(Bid.id == module_data.bid_id).first()
            if not bid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bid not found"
                )
            
            if bid.status != BidStatus.WON:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only create modules for won bids"
                )
            
            # Validate team access
            if user_role == UserRole.SUB_ADMIN.value:
                if bid.team_id != user_team_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Can only create modules for your own team's bids"
                    )
            
            # Check if ANY modules already exist for this bid (Single Module Workflow)
            existing_modules = self.repository.get_by_bid(db, module_data.bid_id)
            if existing_modules:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Modules already exist for this bid. Single module workflow allows only one module per bid. Use bulk endpoint for multiple modules or delete existing modules first."
                )
            
            # Check if receivables already exist for this bid
            existing_receivables = db.query(Receivable).filter(Receivable.bid_id == module_data.bid_id).first()
            if existing_receivables:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create modules: Receivables already exist for this bid. Use PUT API to update existing modules or DELETE receivables first."
                )
            
            # Set order_sequence to 1 for single module
            module_data.order_sequence = 1
            
            module = self.repository.create(db, module_data)
            
            # Update bid to indicate it has modules
            bid.has_modules = True
            db.commit()
            
            return self._to_response(db, module)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating single module: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while creating single module"
            )
    def create_bulk_modules(self, db: Session, bulk_data: ModuleBulkCreate, created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> List[ModuleResponse]:
        """Create multiple modules for a bid."""
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
                    detail="Can only create modules for won bids"
                )
            
            # Validate team access
            if user_role == UserRole.SUB_ADMIN.value:
                if bid.team_id != user_team_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Can only create modules for your own team's bids"
                    )
            
            # Check if any modules already exist for this bid
            existing_modules = self.repository.get_by_bid(db, bulk_data.bid_id)
            if existing_modules:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Modules already exist for this bid. Use PUT API to update existing modules or DELETE them first."
                )
            
            # Check if receivables already exist for this bid
            existing_receivables = db.query(Receivable).filter(Receivable.bid_id == bulk_data.bid_id).first()
            if existing_receivables:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create modules: Receivables already exist for this bid."
                )
            
            modules = self.repository.create_bulk(db, bulk_data)
            
            # Update bid to indicate it has modules
            bid.has_modules = True
            db.commit()
            
            return [self._to_response(db, module) for module in modules]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating bulk modules: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while creating bulk modules"
            )
    
    def get_module(self, db: Session, module_id: UUID, user_id: UUID,
                  user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ModuleResponse]:
        """Get module by ID with access control."""
        module = self.repository.get_by_id(db, module_id)
        if not module:
            return None
        
        # Access control
        if not self._has_access_to_module(db, module, user_role, user_team_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this module"
            )
        
        return self._to_response(db, module)
    
    def get_bid_modules(self, db: Session, bid_id: UUID, user_id: UUID, user_role: str,
                       user_team_id: Optional[UUID] = None) -> BidModulesResponse:
        """Get all modules for a specific bid."""
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
            
            # Get modules
            modules = self.repository.get_by_bid(db, bid_id)
            
            # Check if any module has receivables
            has_receivables = any(
                db.query(Receivable).filter(Receivable.module_id == module.id).first()
                for module in modules
            )
            
            # Calculate total amount
            total_amount = sum(module.module_amount for module in modules)
            
            # Determine permissions
            can_create_modules = not has_receivables and len(modules) == 0
            can_delete_modules = not has_receivables
            
            return BidModulesResponse(
                bid_id=bid.id,
                job_title=bid.job_title,
                client_name=str(bid.client_name),
                total_modules=len(modules),
                total_amount=total_amount,
                modules=[self._to_response(db, module) for module in modules],
                has_receivables=has_receivables,
                can_create_modules=can_create_modules,
                can_delete_modules=can_delete_modules
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bid modules: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while getting bid modules"
            )
    
    def get_modules(self, db: Session, filters: ModuleListFilter, user_id: UUID, user_role: str, 
                   skip: int = 0, limit: int = 20, sort_by: str = "-created_at",
                   user_team_id: Optional[UUID] = None) -> PaginatedResponse[ModuleResponse]:
        """Get modules with filtering, pagination and access control."""
        # Apply access control to filters
        if user_role == UserRole.SUB_ADMIN.value:
            # Sub-admins can only see modules for their team's bids
            pass  # Will be handled in repository layer
        
        result = self.repository.get_all(db, filters, skip, limit, sort_by, user_role, user_team_id)
        
        # Convert items to response format
        response_items = [self._to_response(db, item) for item in result.items]
        
        return PaginatedResponse(
            items=response_items,
            next_cursor=result.next_cursor,
            count=result.count
        )
    
    def update_module(self, db: Session, module_id: UUID, module_data: ModuleUpdate,
                     user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ModuleResponse]:
        """Update module with access control."""
        try:
            module = self.repository.get_by_id(db, module_id)
            if not module:
                return None
            
            # Access control
            if not self._has_access_to_module(db, module, user_role, user_team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this module"
                )
            
            # Check if module has receivables and restrict certain updates
            has_receivable = db.query(Receivable).filter(Receivable.module_id == module_id).first()
            if has_receivable and module_data.module_amount is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change module amount: Receivable exists for this module"
                )
            
            # Validate order sequence uniqueness if being updated
            if module_data.order_sequence is not None:
                existing_module_with_sequence = db.query(ProjectModule).filter(
                    ProjectModule.bid_id == module.bid_id,
                    ProjectModule.order_sequence == module_data.order_sequence,
                    ProjectModule.id != module_id
                ).first()
                
                if existing_module_with_sequence:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Module with order sequence {module_data.order_sequence} already exists for this bid"
                    )
            
            updated_module = self.repository.update(db, module_id, module_data)
            return self._to_response(db, updated_module) if updated_module else None
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating module {module_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating module"
            )
    
    def update_module_status(self, db: Session, module_id: UUID, status_data: ModuleStatusUpdate,
                            user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ModuleResponse]:
        """Update module status with access control."""
        try:
            module = self.repository.get_by_id(db, module_id)
            if not module:
                return None
            
            # Access control
            if not self._has_access_to_module(db, module, user_role, user_team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this module"
                )
            
            # Validate status transition
            if not self._is_valid_status_transition(module.status, status_data.status):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status transition from {module.status.value} to {status_data.status.value}"
                )
            
            # Update module status
            update_data = ModuleUpdate(status=status_data.status)
            updated_module = self.repository.update(db, module_id, update_data)
            return self._to_response(db, updated_module) if updated_module else None
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating module status {module_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating module status"
            )
    
    def delete_module(self, db: Session, module_id: UUID, user_id: UUID,
                     user_role: str, user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Delete module with access control."""
        try:
            module = self.repository.get_by_id(db, module_id)
            if not module:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Module not found"
                )
            
            # Access control
            if not self._has_access_to_module(db, module, user_role, user_team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this module"
                )
            
            # Check if module has receivables
            has_receivable = db.query(Receivable).filter(Receivable.module_id == module_id).first()
            if has_receivable:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete module: Receivable exists for this module. Delete the receivable first."
                )
            
            success = self.repository.delete(db, module_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Module not found"
                )
            
            return SuccessResponse(message="Module deleted successfully")
            
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error deleting module {module_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while deleting module"
            )
    
    def check_bid_status(self, db: Session, bid_id: UUID, user_id: UUID, user_role: str,
                        user_team_id: Optional[UUID] = None) -> BidStatusCheck:
        """Check bid status for module operations."""
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
            
            # Get modules and receivables count
            modules = self.repository.get_by_bid(db, bid_id)
            receivables = db.query(Receivable).filter(Receivable.bid_id == bid_id).all()
            
            has_modules = len(modules) > 0
            has_receivables = len(receivables) > 0
            
            # Determine permissions and generate recommendations
            can_create_modules = not has_receivables
            can_delete_modules = not has_receivables
            
            message = ""
            recommendations = []
            
            if has_modules and has_receivables:
                message = "Bid has modules with receivables. Limited operations available."
                recommendations.extend([
                    "Use PUT API to update existing modules (limited fields)",
                    "Delete receivables first to enable full module management",
                    "Module amounts cannot be changed while receivables exist"
                ])
            elif has_modules and not has_receivables:
                message = "Bid has modules but no receivables. Full module management available."
                recommendations.extend([
                    "You can update or delete existing modules",
                    "You can create receivables for existing modules",
                    "You can add more modules if needed"
                ])
            elif not has_modules and has_receivables:
                message = "Bid has receivables but no modules. Inconsistent state detected."
                recommendations.extend([
                    "This should not happen - receivables should reference modules",
                    "Contact system administrator"
                ])
            else:
                message = "Bid has no modules or receivables. Ready for module creation."
                recommendations.extend([
                    "Create single module for single payment workflow",
                    "Create multiple modules for module-based payment workflow",
                    "Ensure bid status is 'won' before creating modules"
                ])
            
            return BidStatusCheck(
                bid_id=bid.id,
                job_title=bid.job_title,
                has_modules=has_modules,
                module_count=len(modules),
                has_receivables=has_receivables,
                receivable_count=len(receivables),
                can_create_modules=can_create_modules,
                can_delete_modules=can_delete_modules,
                message=message,
                recommendations=recommendations
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking bid status: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while checking bid status"
            )
    
    def _has_access_to_module(self, db: Session, module: ProjectModule, user_role: str, user_team_id: Optional[UUID]) -> bool:
        """Check if user has access to the module."""
        if user_role == UserRole.ADMIN.value:
            return True
        elif user_role == UserRole.SUB_ADMIN.value:
            # Get bid to check team
            bid = db.query(Bid).filter(Bid.id == module.bid_id).first()
            return bid and bid.team_id == user_team_id
        else:
            return False  # Members don't have access to modules
    
    def _is_valid_status_transition(self, current_status: ModuleStatus, new_status: ModuleStatus) -> bool:
        """Validate status transitions."""
        valid_transitions = {
            ModuleStatus.PENDING: [ModuleStatus.IN_PROGRESS, ModuleStatus.COMPLETED],
            ModuleStatus.IN_PROGRESS: [ModuleStatus.COMPLETED, ModuleStatus.PENDING],
            ModuleStatus.COMPLETED: [ModuleStatus.PAID, ModuleStatus.IN_PROGRESS],
            ModuleStatus.PAID: []  # No transitions from paid
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    def _to_response(self, db: Session, module: ProjectModule) -> ModuleResponse:
        """Convert ProjectModule model to ModuleResponse schema."""
        # Get bid title
        bid = db.query(Bid).filter(Bid.id == module.bid_id).first()
        bid_title = bid.job_title if bid else None
        
        # Check if receivable exists
        receivable = db.query(Receivable).filter(Receivable.module_id == module.id).first()
        has_receivable = receivable is not None
        receivable_id = receivable.id if receivable else None
        
        return ModuleResponse(
            id=module.id,
            bid_id=module.bid_id,
            module_name=module.module_name,
            description=module.description,
            module_amount=module.module_amount,
            order_sequence=module.order_sequence,
            status=module.status,
            created_at=module.created_at,
            updated_at=module.updated_at,
            bid_title=bid_title,
            has_receivable=has_receivable,
            receivable_id=receivable_id
        )