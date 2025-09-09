from sqlalchemy.orm import Query
from sqlalchemy import desc, asc, and_, or_
from models.models import ProjectModule, Bid, ModuleStatus, Receivable
from schemas.module import ModuleListFilter
from typing import Type, Any
import logging

logger = logging.getLogger(__name__)


def _apply_module_filters(query: Query, filters: ModuleListFilter) -> Query:
    """Apply filters to module query."""
    try:
        # Bid filter
        if filters.bid_id:
            query = query.filter(ProjectModule.bid_id == filters.bid_id)
        
        # Status filter
        if filters.status:
            query = query.filter(ProjectModule.status == filters.status)
        
        # Has receivable filter
        if filters.has_receivable is not None:
            if filters.has_receivable:
                # Modules that have receivables
                query = query.join(Receivable, ProjectModule.id == Receivable.module_id)
            else:
                # Modules that don't have receivables
                query = query.outerjoin(Receivable, ProjectModule.id == Receivable.module_id).filter(
                    Receivable.id.is_(None)
                )
        
        return query
        
    except Exception as e:
        logger.error(f"Error applying module filters: {e}")
        return query


def _apply_sorting_generic(query: Query, sort_by: str, model_class: Type[Any]) -> Query:
    """Apply sorting to query with support for module-specific fields."""
    try:
        # Parse sort field and direction
        if sort_by.startswith('-'):
            field_name = sort_by[1:]
            direction = desc
        else:
            field_name = sort_by
            direction = asc
        
        # Handle special cases for modules
        if model_class == ProjectModule:
            if field_name == 'bid_title':
                # Sort by job title from bid
                query = query.join(ProjectModule.bid)
                return query.order_by(direction(Bid.job_title))
            
            elif field_name == 'client_name':
                # Sort by client name from bid
                query = query.join(ProjectModule.bid)
                return query.order_by(direction(Bid.client_name))
            
            elif field_name == 'team_name':
                # Sort by team name through bid
                from models.models import Team
                query = query.join(ProjectModule.bid).join(Bid.team)
                return query.order_by(direction(Team.name))
        
        # Default sorting for model fields
        if hasattr(model_class, field_name):
            field = getattr(model_class, field_name)
            return query.order_by(direction(field))
        else:
            # Fallback to default sorting
            logger.warning(f"Unknown sort field: {field_name}, using default sort")
            return query.order_by(desc(model_class.created_at))
            
    except Exception as e:
        logger.error(f"Error applying sorting: {e}")
        # Fallback to default sorting
        return query.order_by(desc(model_class.created_at))


def validate_module_filters(filters: ModuleListFilter) -> bool:
    """Validate module filters."""
    try:
        # Status validation
        if filters.status and filters.status not in ModuleStatus:
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating filters: {e}")
        return False


def get_module_sort_options() -> list:
    """Get available sort options for modules."""
    return [
        'created_at',
        '-created_at',
        'updated_at',
        '-updated_at',
        'module_name',
        '-module_name',
        'module_amount',
        '-module_amount',
        'order_sequence',
        '-order_sequence',
        'status',
        '-status',
        'bid_title',
        '-bid_title',
        'client_name',
        '-client_name',
        'team_name',
        '-team_name'
    ]


def build_module_query_conditions(filters: ModuleListFilter) -> list:
    """Build a list of query conditions for modules."""
    conditions = []
    
    try:
        if filters.bid_id:
            conditions.append(ProjectModule.bid_id == filters.bid_id)
        
        if filters.status:
            conditions.append(ProjectModule.status == filters.status)
        
        return conditions
        
    except Exception as e:
        logger.error(f"Error building query conditions: {e}")
        return []


def get_module_summary_stats(query: Query) -> dict:
    """Get summary statistics from a module query."""
    try:
        from sqlalchemy import func, case
        
        stats = query.with_entities(
            func.count(ProjectModule.id).label('total_count'),
            func.sum(ProjectModule.module_amount).label('total_amount'),
            func.avg(ProjectModule.module_amount).label('avg_amount'),
            func.sum(
                case(
                    (ProjectModule.status == ModuleStatus.PENDING, ProjectModule.module_amount),
                    else_=0
                )
            ).label('pending_amount'),
            func.sum(
                case(
                    (ProjectModule.status == ModuleStatus.IN_PROGRESS, ProjectModule.module_amount),
                    else_=0
                )
            ).label('in_progress_amount'),
            func.sum(
                case(
                    (ProjectModule.status == ModuleStatus.COMPLETED, ProjectModule.module_amount),
                    else_=0
                )
            ).label('completed_amount'),
            func.sum(
                case(
                    (ProjectModule.status == ModuleStatus.PAID, ProjectModule.module_amount),
                    else_=0
                )
            ).label('paid_amount')
        ).first()
        
        return {
            'total_count': stats.total_count or 0,
            'total_amount': float(stats.total_amount or 0),
            'avg_amount': float(stats.avg_amount or 0),
            'pending_amount': float(stats.pending_amount or 0),
            'in_progress_amount': float(stats.in_progress_amount or 0),
            'completed_amount': float(stats.completed_amount or 0),
            'paid_amount': float(stats.paid_amount or 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting summary stats: {e}")
        return {
            'total_count': 0,
            'total_amount': 0.0,
            'avg_amount': 0.0,
            'pending_amount': 0.0,
            'in_progress_amount': 0.0,
            'completed_amount': 0.0,
            'paid_amount': 0.0
        }


def filter_modules_by_status(query: Query, status: ModuleStatus) -> Query:
    """Filter query to show only modules with specific status."""
    return query.filter(ProjectModule.status == status)


def filter_modules_with_receivables(query: Query) -> Query:
    """Filter query to show only modules that have receivables."""
    return query.join(Receivable, ProjectModule.id == Receivable.module_id)


def filter_modules_without_receivables(query: Query) -> Query:
    """Filter query to show only modules that don't have receivables."""
    return query.outerjoin(Receivable, ProjectModule.id == Receivable.module_id).filter(
        Receivable.id.is_(None)
    )


def group_modules_by_status(query: Query) -> Query:
    """Group modules by status for summary reports."""
    from sqlalchemy import func
    
    return query.with_entities(
        ProjectModule.status,
        func.count(ProjectModule.id).label('module_count'),
        func.sum(ProjectModule.module_amount).label('total_amount'),
        func.avg(ProjectModule.module_amount).label('avg_amount')
    ).group_by(ProjectModule.status)


def group_modules_by_bid(query: Query) -> Query:
    """Group modules by bid for analysis."""
    from sqlalchemy import func
    
    return query.join(ProjectModule.bid).with_entities(
        Bid.id.label('bid_id'),
        Bid.job_title,
        Bid.client_name,
        func.count(ProjectModule.id).label('module_count'),
        func.sum(ProjectModule.module_amount).label('total_amount')
    ).group_by(Bid.id, Bid.job_title, Bid.client_name)


def search_modules_by_text(query: Query, search_term: str) -> Query:
    """Search modules by text in module name, description, or bid title."""
    search_pattern = f"%{search_term}%"
    
    return query.join(ProjectModule.bid).filter(
        or_(
            ProjectModule.module_name.ilike(search_pattern),
            ProjectModule.description.ilike(search_pattern),
            Bid.job_title.ilike(search_pattern),
            Bid.client_name.ilike(search_pattern)
        )
    )


def validate_module_order_sequence(db_session, bid_id: str, order_sequence: int, module_id: str = None) -> bool:
    """Validate that order sequence is unique within a bid."""
    try:
        query = db_session.query(ProjectModule).filter(
            ProjectModule.bid_id == bid_id,
            ProjectModule.order_sequence == order_sequence
        )
        
        # Exclude current module if updating
        if module_id:
            query = query.filter(ProjectModule.id != module_id)
        
        existing = query.first()
        return existing is None
        
    except Exception as e:
        logger.error(f"Error validating order sequence: {e}")
        return False


def get_next_order_sequence(db_session, bid_id: str) -> int:
    """Get the next available order sequence for a bid."""
    try:
        from sqlalchemy import func
        
        max_sequence = db_session.query(
            func.max(ProjectModule.order_sequence)
        ).filter(ProjectModule.bid_id == bid_id).scalar()
        
        return (max_sequence or 0) + 1
        
    except Exception as e:
        logger.error(f"Error getting next order sequence: {e}")
        return 1