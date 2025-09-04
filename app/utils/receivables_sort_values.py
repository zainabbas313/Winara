# utils/sort_values.py - Updated receivable filtering functions

from sqlalchemy.orm import Query
from sqlalchemy import desc, asc, and_, or_
from models.models import Receivable, Bid, ProjectModule, PaymentType, ReceivableStatus
from schemas.receivable import ReceivableListFilter
from typing import Type, Any
import logging

logger = logging.getLogger(__name__)


def _apply_receivable_filters(query: Query, filters: ReceivableListFilter) -> Query:
    """Apply filters to receivable query with support for modules."""
    try:
        # Team filter - filter through bid
        if filters.team_id:
            query = query.join(Receivable.bid).filter(Bid.team_id == filters.team_id)
        
        # Status filter
        if filters.status:
            query = query.filter(Receivable.status == filters.status)
        
        # Payment type filter
        if filters.payment_type:
            query = query.filter(Receivable.payment_type == filters.payment_type)
        
        # Date range filters
        if filters.date_from:
            query = query.filter(Receivable.expected_payment_date >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Receivable.expected_payment_date <= filters.date_to)
        
        # Client name filter - search through bid
        if filters.client_name:
            if not query._legacy_facade():
                # If not already joined with Bid, join it
                query = query.join(Receivable.bid)
            query = query.filter(Bid.client_name.ilike(f"%{filters.client_name}%"))
        
        # Module filter
        if filters.module_id:
            query = query.filter(Receivable.module_id == filters.module_id)
        
        return query
        
    except Exception as e:
        logger.error(f"Error applying receivable filters: {e}")
        return query


def _apply_sorting_generic(query: Query, sort_by: str, model_class: Type[Any]) -> Query:
    """Apply sorting to query with support for receivable-specific fields."""
    try:
        # Parse sort field and direction
        if sort_by.startswith('-'):
            field_name = sort_by[1:]
            direction = desc
        else:
            field_name = sort_by
            direction = asc
        
        # Handle special cases for receivables
        if model_class == Receivable:
            if field_name == 'client_name':
                # Sort by client name from bid
                query = query.join(Receivable.bid)
                return query.order_by(direction(Bid.client_name))
            
            elif field_name == 'project_title':
                # Sort by job title from bid
                query = query.join(Receivable.bid)
                return query.order_by(direction(Bid.job_title))
            
            elif field_name == 'module_name':
                # Sort by module name
                query = query.outerjoin(Receivable.module)
                return query.order_by(direction(ProjectModule.module_name))
            
            elif field_name == 'team_name':
                # Sort by team name through bid
                from models.models import Team
                query = query.join(Receivable.bid).join(Bid.team)
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


def validate_receivable_filters(filters: ReceivableListFilter) -> bool:
    """Validate receivable filters."""
    try:
        # Date range validation
        if filters.date_from and filters.date_to:
            if filters.date_from > filters.date_to:
                return False
        
        # Payment type validation
        if filters.payment_type and filters.payment_type not in PaymentType:
            return False
        
        # Status validation
        if filters.status and filters.status not in ReceivableStatus:
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating filters: {e}")
        return False


def get_receivable_sort_options() -> list:
    """Get available sort options for receivables."""
    return [
        'created_at',
        '-created_at',
        'updated_at',
        '-updated_at',
        'expected_payment_date',
        '-expected_payment_date',
        'contract_value',
        '-contract_value',
        'status',
        '-status',
        'payment_type',
        '-payment_type',
        'client_name',
        '-client_name',
        'project_title',
        '-project_title',
        'module_name',
        '-module_name',
        'team_name',
        '-team_name'
    ]


def build_receivable_query_conditions(filters: ReceivableListFilter) -> list:
    """Build a list of query conditions for receivables."""
    conditions = []
    
    try:
        if filters.status:
            conditions.append(Receivable.status == filters.status)
        
        if filters.payment_type:
            conditions.append(Receivable.payment_type == filters.payment_type)
        
        if filters.date_from:
            conditions.append(Receivable.expected_payment_date >= filters.date_from)
        
        if filters.date_to:
            conditions.append(Receivable.expected_payment_date <= filters.date_to)
        
        if filters.module_id:
            conditions.append(Receivable.module_id == filters.module_id)
        
        return conditions
        
    except Exception as e:
        logger.error(f"Error building query conditions: {e}")
        return []


def get_receivable_summary_stats(query: Query) -> dict:
    """Get summary statistics from a receivable query."""
    try:
        from sqlalchemy import func, case
        
        stats = query.with_entities(
            func.count(Receivable.id).label('total_count'),
            func.sum(Receivable.contract_value).label('total_value'),
            func.sum(
                case(
                    (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                    else_=0
                )
            ).label('paid_value'),
            func.sum(
                case(
                    (Receivable.status == ReceivableStatus.PENDING, Receivable.contract_value),
                    else_=0
                )
            ).label('pending_value'),
            func.sum(
                case(
                    (Receivable.payment_type == PaymentType.SINGLE, Receivable.contract_value),
                    else_=0
                )
            ).label('single_payment_value'),
            func.sum(
                case(
                    (Receivable.payment_type == PaymentType.MODULE_BASED, Receivable.contract_value),
                    else_=0
                )
            ).label('module_payment_value')
        ).first()
        
        return {
            'total_count': stats.total_count or 0,
            'total_value': float(stats.total_value or 0),
            'paid_value': float(stats.paid_value or 0),
            'pending_value': float(stats.pending_value or 0),
            'single_payment_value': float(stats.single_payment_value or 0),
            'module_payment_value': float(stats.module_payment_value or 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting summary stats: {e}")
        return {
            'total_count': 0,
            'total_value': 0.0,
            'paid_value': 0.0,
            'pending_value': 0.0,
            'single_payment_value': 0.0,
            'module_payment_value': 0.0
        }


def filter_overdue_receivables(query: Query) -> Query:
    """Filter query to show only overdue receivables."""
    from datetime import date
    
    today = date.today()
    return query.filter(
        and_(
            Receivable.expected_payment_date < today,
            Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
        )
    )


def filter_upcoming_receivables(query: Query, days_ahead: int = 30) -> Query:
    """Filter query to show receivables due within specified days."""
    from datetime import date, timedelta
    
    today = date.today()
    future_date = today + timedelta(days=days_ahead)
    
    return query.filter(
        and_(
            Receivable.expected_payment_date >= today,
            Receivable.expected_payment_date <= future_date,
            Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
        )
    )


def group_receivables_by_client(query: Query) -> Query:
    """Group receivables by client for summary reports."""
    from sqlalchemy import func
    
    return query.join(Receivable.bid).with_entities(
        Bid.client_name,
        func.count(Receivable.id).label('receivable_count'),
        func.sum(Receivable.contract_value).label('total_value'),
        func.sum(
            case(
                (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                else_=0
            )
        ).label('paid_value')
    ).group_by(Bid.client_name)


def group_receivables_by_payment_type(query: Query) -> Query:
    """Group receivables by payment type for analysis."""
    from sqlalchemy import func
    
    return query.with_entities(
        Receivable.payment_type,
        func.count(Receivable.id).label('receivable_count'),
        func.sum(Receivable.contract_value).label('total_value'),
        func.avg(Receivable.contract_value).label('avg_value')
    ).group_by(Receivable.payment_type)


def search_receivables_by_text(query: Query, search_term: str) -> Query:
    """Search receivables by text in client name, project title, or module name."""
    search_pattern = f"%{search_term}%"
    
    return query.join(Receivable.bid).outerjoin(Receivable.module).filter(
        or_(
            Bid.client_name.ilike(search_pattern),
            Bid.job_title.ilike(search_pattern),
            ProjectModule.module_name.ilike(search_pattern),
            ProjectModule.description.ilike(search_pattern)
        )
    )