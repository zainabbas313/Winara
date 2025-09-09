from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.models import ProjectModule, ModuleStatus
from schemas.module import ModuleCreate, ModuleUpdate, ModuleListFilter, ModuleBulkCreate
from schemas.common import PaginatedResponse


class IModuleRepository(ABC):
    """Interface for module repository operations."""
    
    @abstractmethod
    def create(self, db: Session, module_data: ModuleCreate) -> ProjectModule:
        """Create a new project module."""
        pass
    
    @abstractmethod
    def create_bulk(self, db: Session, bulk_data: ModuleBulkCreate) -> List[ProjectModule]:
        """Create multiple modules for a bid."""
        pass
    
    @abstractmethod
    def get_by_id(self, db: Session, module_id: UUID) -> Optional[ProjectModule]:
        """Get module by ID with related data."""
        pass
    
    @abstractmethod
    def get_by_bid(self, db: Session, bid_id: UUID) -> List[ProjectModule]:
        """Get all modules for a bid."""
        pass
    
    @abstractmethod
    def get_all(self, db: Session, filters: ModuleListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at", user_role: str = None,
                user_team_id: Optional[UUID] = None) -> PaginatedResponse:
        """Get all modules with filters and pagination."""
        pass
    
    @abstractmethod
    def update(self, db: Session, module_id: UUID, module_data: ModuleUpdate) -> Optional[ProjectModule]:
        """Update module."""
        pass
    
    @abstractmethod
    def delete(self, db: Session, module_id: UUID) -> bool:
        """Delete module."""
        pass
    
    @abstractmethod
    def get_by_status(self, db: Session, status: ModuleStatus, 
                     skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get modules by status."""
        pass
    
    @abstractmethod
    def get_statistics(self, db: Session, bid_id: Optional[UUID] = None, 
                      team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get module statistics."""
        pass
    
    @abstractmethod
    def get_modules_without_receivables(self, db: Session, team_id: Optional[UUID] = None) -> List[ProjectModule]:
        """Get modules that don't have receivables yet."""
        pass
    
    @abstractmethod
    def get_bid_module_summary(self, db: Session, bid_id: UUID) -> Dict[str, Any]:
        """Get summary of modules for a specific bid."""
        pass
    
    @abstractmethod
    def reorder_modules(self, db: Session, bid_id: UUID, module_orders: List[Dict[str, int]]) -> bool:
        """Reorder modules by updating their order_sequence."""
        pass