from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc
from .base_repository import BaseRepository
from models.models import ProjectModule, ModuleStatus, Bid, UserRole
from schemas.module import ModuleCreate, ModuleUpdate, ModuleListFilter, ModuleBulkCreate
from schemas.common import PaginatedResponse
from interface.Irepositories.module_repository import IModuleRepository
from utils.module_sort_values import _apply_sorting_generic, _apply_module_filters
import logging

logger = logging.getLogger(__name__)


class ModuleRepository(BaseRepository[ProjectModule], IModuleRepository):
    def __init__(self):
        super().__init__(ProjectModule)

    def create(self, db: Session, module_data: ModuleCreate) -> ProjectModule:
        """Create a new project module."""
        try:
            module_dict = module_data.dict()
            return super().create(db, **module_dict)
        except Exception as e:
            logger.error(f"Error creating module: {e}")
            raise

    def create_bulk(self, db: Session, bulk_data: ModuleBulkCreate) -> List[ProjectModule]:
        """Create multiple modules for a bid."""
        try:
            modules = []
            
            for module_data in bulk_data.modules:
                module_dict = module_data.dict()
                module_dict['bid_id'] = bulk_data.bid_id
                
                module = ProjectModule(**module_dict)
                db.add(module)
                modules.append(module)
            
            db.commit()
            
            # Refresh all modules to get their IDs
            for module in modules:
                db.refresh(module)
            
            return modules
        except Exception as e:
            logger.error(f"Error creating bulk modules: {e}")
            db.rollback()
            raise

    def get_by_id(self, db: Session, module_id: UUID) -> Optional[ProjectModule]:
        """Get module by ID with related data."""
        try:
            return db.query(ProjectModule).options(
                joinedload(ProjectModule.bid)
            ).filter(ProjectModule.id == module_id).first()
        except Exception as e:
            logger.error(f"Error getting module {module_id}: {e}")
            return None

    def get_by_bid(self, db: Session, bid_id: UUID) -> List[ProjectModule]:
        """Get all modules for a bid."""
        try:
            return db.query(ProjectModule).options(
                joinedload(ProjectModule.bid)
            ).filter(ProjectModule.bid_id == bid_id).order_by(ProjectModule.order_sequence).all()
        except Exception as e:
            logger.error(f"Error getting modules by bid {bid_id}: {e}")
            return []

    def get_all(self, db: Session, filters: ModuleListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at", user_role: str = None,
                user_team_id: Optional[UUID] = None) -> PaginatedResponse:
        """Get all modules with filters and pagination."""
        try:
            query = db.query(ProjectModule).options(
                joinedload(ProjectModule.bid)
            )
            
            # Apply access control
            if user_role == UserRole.SUB_ADMIN.value and user_team_id:
                query = query.join(ProjectModule.bid).filter(Bid.team_id == user_team_id)
            
            # Apply filters
            query = self._apply_module_filters(query, filters)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply sorting using the utility function
            query = _apply_sorting_generic(query, sort_by, ProjectModule)
            
            # Apply pagination
            items = query.offset(skip).limit(limit).all()
            
            # Build next cursor if needed
            next_cursor = None
            if len(items) == limit and skip + limit < total_count:
                next_cursor = f"offset:{skip + limit}"
            
            return PaginatedResponse(
                items=items,
                next_cursor=next_cursor,
                count=len(items)
            )
        except Exception as e:
            logger.error(f"Error getting modules: {e}")
            return PaginatedResponse(
                items=[], 
                next_cursor=None, 
                count=0
            )

    def _apply_module_filters(self, query, filters: ModuleListFilter):
        """Apply filters to module query."""
        if filters.bid_id:
            query = query.filter(ProjectModule.bid_id == filters.bid_id)
        
        if filters.status:
            query = query.filter(ProjectModule.status == filters.status)
        
        if filters.has_receivable is not None:
            from models.models import Receivable
            if filters.has_receivable:
                # Modules that have receivables
                query = query.join(Receivable, ProjectModule.id == Receivable.module_id)
            else:
                # Modules that don't have receivables
                query = query.outerjoin(Receivable, ProjectModule.id == Receivable.module_id).filter(
                    Receivable.id.is_(None)
                )
        
        return query

    def update(self, db: Session, module_id: UUID, module_data: ModuleUpdate) -> Optional[ProjectModule]:
        """Update module."""
        try:
            module = self.get_by_id(db, module_id)
            if not module:
                return None
            
            update_data = module_data.dict(exclude_unset=True)
            return super().update(db, module, **update_data)
        except Exception as e:
            logger.error(f"Error updating module {module_id}: {e}")
            return None

    def delete(self, db: Session, module_id: UUID) -> bool:
        """Delete module."""
        return super().delete(db, module_id)

    def get_by_status(self, db: Session, status: ModuleStatus, 
                     skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get modules by status."""
        filters = ModuleListFilter(status=status)
        return self.get_all(db, filters, skip, limit)

    def get_statistics(self, db: Session, bid_id: Optional[UUID] = None, 
                      team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get module statistics."""
        try:
            query = db.query(ProjectModule)
            
            # Apply filters
            if bid_id:
                query = query.filter(ProjectModule.bid_id == bid_id)
            
            if team_id:
                query = query.join(ProjectModule.bid).filter(Bid.team_id == team_id)
            
            # Get basic counts and totals
            stats = query.with_entities(
                func.count(ProjectModule.id).label('total_modules'),
                func.sum(ProjectModule.module_amount).label('total_amount'),
                func.avg(ProjectModule.module_amount).label('avg_amount')
            ).first()
            
            # Get status breakdown
            status_breakdown = query.with_entities(
                ProjectModule.status,
                func.count(ProjectModule.id).label('count'),
                func.sum(ProjectModule.module_amount).label('amount')
            ).group_by(ProjectModule.status).all()
            
            # Get modules with/without receivables count
            from models.models import Receivable
            
            modules_with_receivables = query.join(
                Receivable, ProjectModule.id == Receivable.module_id
            ).count()
            
            modules_without_receivables = stats.total_modules - modules_with_receivables
            
            return {
                'total_modules': stats.total_modules or 0,
                'total_amount': stats.total_amount or 0,
                'avg_module_amount': stats.avg_amount or 0,
                'modules_with_receivables': modules_with_receivables,
                'modules_without_receivables': modules_without_receivables,
                'by_status': [
                    {
                        'status': breakdown.status.value,
                        'count': breakdown.count,
                        'amount': float(breakdown.amount or 0)
                    }
                    for breakdown in status_breakdown
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting module statistics: {e}")
            return {}

    def get_modules_without_receivables(self, db: Session, team_id: Optional[UUID] = None) -> List[ProjectModule]:
        """Get modules that don't have receivables yet."""
        try:
            from models.models import Receivable
            
            query = db.query(ProjectModule).options(
                joinedload(ProjectModule.bid)
            ).outerjoin(
                Receivable, ProjectModule.id == Receivable.module_id
            ).filter(Receivable.id.is_(None))
            
            if team_id:
                query = query.join(ProjectModule.bid).filter(Bid.team_id == team_id)
            
            return query.all()
            
        except Exception as e:
            logger.error(f"Error getting modules without receivables: {e}")
            return []

    def get_bid_module_summary(self, db: Session, bid_id: UUID) -> Dict[str, Any]:
        """Get summary of modules for a specific bid."""
        try:
            modules = self.get_by_bid(db, bid_id)
            
            if not modules:
                return {
                    'total_modules': 0,
                    'total_amount': 0,
                    'by_status': [],
                    'modules_with_receivables': 0,
                    'modules_without_receivables': 0
                }
            
            from models.models import Receivable
            
            # Calculate totals
            total_amount = sum(module.module_amount for module in modules)
            
            # Get receivables count
            modules_with_receivables = db.query(func.count(Receivable.id)).filter(
                Receivable.module_id.in_([module.id for module in modules])
            ).scalar() or 0
            
            # Status breakdown
            status_counts = {}
            for module in modules:
                status = module.status.value
                if status not in status_counts:
                    status_counts[status] = {'count': 0, 'amount': 0}
                status_counts[status]['count'] += 1
                status_counts[status]['amount'] += float(module.module_amount)
            
            return {
                'total_modules': len(modules),
                'total_amount': float(total_amount),
                'by_status': [
                    {'status': status, 'count': data['count'], 'amount': data['amount']}
                    for status, data in status_counts.items()
                ],
                'modules_with_receivables': modules_with_receivables,
                'modules_without_receivables': len(modules) - modules_with_receivables
            }
            
        except Exception as e:
            logger.error(f"Error getting bid module summary: {e}")
            return {}

    def reorder_modules(self, db: Session, bid_id: UUID, module_orders: List[Dict[str, int]]) -> bool:
        """Reorder modules by updating their order_sequence."""
        try:
            for item in module_orders:
                module_id = item['module_id']
                new_sequence = item['order_sequence']
                
                module = db.query(ProjectModule).filter(
                    ProjectModule.id == module_id,
                    ProjectModule.bid_id == bid_id
                ).first()
                
                if module:
                    module.order_sequence = new_sequence
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error reordering modules: {e}")
            db.rollback()
            return False