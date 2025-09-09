from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from schemas.module import (
    ModuleCreate, ModuleUpdate, ModuleResponse, ModuleListFilter,
    ModuleBulkCreate, ModuleStatusUpdate, BidModulesResponse, BidStatusCheck
)
from schemas.common import SuccessResponse, PaginatedResponse


class IModuleService(ABC):
    """Interface for module service operations."""
    
    @abstractmethod
    def create_module(self, db: Session, module_data: ModuleCreate, 
                     created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> ModuleResponse:
        """Create a new project module."""
        pass
    
    @abstractmethod
    def create_single_module(self, db: Session, module_data: ModuleCreate, 
                            created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> ModuleResponse:
        """Create a single module for a bid - Single Module Workflow."""
        pass
    
    @abstractmethod
    def create_bulk_modules(self, db: Session, bulk_data: ModuleBulkCreate,
                           created_by_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> List[ModuleResponse]:
        """Create multiple modules for a bid."""
        pass
    
    @abstractmethod
    def get_module(self, db: Session, module_id: UUID, user_id: UUID,
                  user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ModuleResponse]:
        """Get module by ID with access control."""
        pass
    
    @abstractmethod
    def get_bid_modules(self, db: Session, bid_id: UUID, user_id: UUID, user_role: str,
                       user_team_id: Optional[UUID] = None) -> BidModulesResponse:
        """Get all modules for a specific bid."""
        pass
    
    @abstractmethod
    def get_modules(self, db: Session, filters: ModuleListFilter, user_id: UUID, user_role: str, 
                   skip: int = 0, limit: int = 20, sort_by: str = "-created_at",
                   user_team_id: Optional[UUID] = None) -> PaginatedResponse[ModuleResponse]:
        """Get modules with filtering, pagination and access control."""
        pass
    
    @abstractmethod
    def update_module(self, db: Session, module_id: UUID, module_data: ModuleUpdate,
                     user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ModuleResponse]:
        """Update module with access control."""
        pass
    
    @abstractmethod
    def update_module_status(self, db: Session, module_id: UUID, status_data: ModuleStatusUpdate,
                            user_id: UUID, user_role: str, user_team_id: Optional[UUID] = None) -> Optional[ModuleResponse]:
        """Update module status with access control."""
        pass
    
    @abstractmethod
    def delete_module(self, db: Session, module_id: UUID, user_id: UUID,
                     user_role: str, user_team_id: Optional[UUID] = None) -> SuccessResponse:
        """Delete module with access control."""
        pass
    
    @abstractmethod
    def check_bid_status(self, db: Session, bid_id: UUID, user_id: UUID, user_role: str,
                        user_team_id: Optional[UUID] = None) -> BidStatusCheck:
        """Check bid status for module operations."""
        pass