# utils/receivables_sort_values.py - Updated receivable filtering functions

from sqlalchemy.orm import Query
from sqlalchemy import desc, asc, and_, or_, func, case
from models.models import Receivable, Bid, ProjectModule, PaymentType, ReceivableStatus, Team
from schemas.receivable import ReceivableListFilter
from typing import Type, Any, Optional
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


def _apply_receivable_filters(query: Query, filters: ReceivableListFilter) -> Query:
    """Apply filters to receivable query with enhanced module support."""
    try:
        # Team filter - filter through bid
        if filters.team_id:
            if not _has_bid_join(query):
                query = query.join(Receivable.bid)
            query = query.filter(Bid.team_id == filters.team_id)
        
        # Bid filter - filter by specific bid
        if filters.bid_id:
            query = query.filter(Receivable.bid_id == filters.bid_id)
        
        # Status filter
        if filters.status:
            query = query.filter(Receivable.status == filters.status)
        
        # Payment type filter (though should mostly be MODULE_BASED now)
        if filters.payment_type:
            query = query.filter(Receivable.payment_type == filters.payment_type)
        
        # Date range filters
        if filters.date_from:
            query = query.filter(Receivable.expected_payment_date >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Receivable.expected_payment_date <= filters.date_to)
        
        # Client name filter - search through bid
        if filters.client_name:
            if not _has_bid_join(query):
                query = query.join(Receivable.bid)
            query = query.filter(Bid.client_name.ilike(f"%{filters.client_name}%"))
        
        # Module filter - specific module
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
                if not _has_bid_join(query):
                    query = query.join(Receivable.bid)
                return query.order_by(direction(Bid.client_name))
            
            elif field_name == 'project_title':
                # Sort by job title from bid
                if not _has_bid_join(query):
                    query = query.join(Receivable.bid)
                return query.order_by(direction(Bid.job_title))
            
            elif field_name == 'module_name':
                # Sort by module name
                if not _has_module_join(query):
                    query = query.join(Receivable.module)
                return query.order_by(direction(ProjectModule.module_name))
            
            elif field_name == 'module_sequence':
                # Sort by module order sequence
                if not _has_module_join(query):
                    query = query.join(Receivable.module)
                return query.order_by(direction(ProjectModule.order_sequence))
            
            elif field_name == 'team_name':
                # Sort by team name through bid
                if not _has_bid_join(query):
                    query = query.join(Receivable.bid)
                query = query.join(Bid.team)
                return query.order_by(direction(Team.name))
            
            elif field_name == 'days_overdue':
                # Sort by calculated overdue days
                today = date.today()
                return query.order_by(
                    direction(
                        case(
                            (
                                and_(
                                    Receivable.expected_payment_date < today,
                                    Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
                                ),
                                func.date_part('day', today - Receivable.expected_payment_date)
                            ),
                            else_=0
                        )
                    )
                )
            
            elif field_name == 'payment_delay':
                # Sort by payment delay (for paid receivables)
                return query.order_by(
                    direction(
                        case(
                            (
                                and_(
                                    Receivable.status == ReceivableStatus.PAID,
                                    Receivable.actual_payment_date.isnot(None)
                                ),
                                func.date_part('day', Receivable.actual_payment_date - Receivable.expected_payment_date)
                            ),
                            else_=None
                        )
                    )
                )
        
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


def _has_bid_join(query: Query) -> bool:
    """Check if query already has bid join."""
    try:
        # Simple check - this might need refinement based on your SQLAlchemy version
        return any('bid' in str(join).lower() for join in query.column_descriptions if hasattr(join, 'name'))
    except:
        # If we can't determine, assume no join and let SQLAlchemy handle duplicates
        return False


def _has_module_join(query: Query) -> bool:
    """Check if query already has module join."""
    try:
        # Simple check - this might need refinement based on your SQLAlchemy version
        return any('module' in str(join).lower() for join in query.column_descriptions if hasattr(join, 'name'))
    except:
        # If we can't determine, assume no join and let SQLAlchemy handle duplicates
        return False


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
        'actual_payment_date',
        '-actual_payment_date',
        'contract_value',
        '-contract_value',
        'payment_amount',
        '-payment_amount',
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
        'module_sequence',
        '-module_sequence',
        'team_name',
        '-team_name',
        'days_overdue',
        '-days_overdue',
        'payment_delay',
        '-payment_delay'
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
        
        if filters.bid_id:
            conditions.append(Receivable.bid_id == filters.bid_id)
        
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
                    (Receivable.status == ReceivableStatus.PARTIAL, Receivable.contract_value),
                    else_=0
                )
            ).label('partial_value'),
            func.sum(
                case(
                    (Receivable.status == ReceivableStatus.OVERDUE, Receivable.contract_value),
                    else_=0
                )
            ).label('overdue_value'),
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
            'partial_value': float(stats.partial_value or 0),
            'overdue_value': float(stats.overdue_value or 0),
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
            'partial_value': 0.0,
            'overdue_value': 0.0,
            'single_payment_value': 0.0,
            'module_payment_value': 0.0
        }


def filter_overdue_receivables(query: Query) -> Query:
    """Filter query to show only overdue receivables."""
    today = date.today()
    return query.filter(
        and_(
            Receivable.expected_payment_date < today,
            Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
        )
    )


def filter_upcoming_receivables(query: Query, days_ahead: int = 30) -> Query:
    """Filter query to show receivables due within specified days."""
    today = date.today()
    future_date = today + timedelta(days=days_ahead)
    
    return query.filter(
        and_(
            Receivable.expected_payment_date >= today,
            Receivable.expected_payment_date <= future_date,
            Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
        )
    )


def filter_paid_receivables(query: Query) -> Query:
    """Filter query to show only paid receivables."""
    return query.filter(Receivable.status == ReceivableStatus.PAID)


def filter_unpaid_receivables(query: Query) -> Query:
    """Filter query to show only unpaid receivables."""
    return query.filter(
        Receivable.status.in_([
            ReceivableStatus.PENDING, 
            ReceivableStatus.PARTIAL, 
            ReceivableStatus.OVERDUE
        ])
    )


def filter_module_based_receivables(query: Query) -> Query:
    """Filter query to show only module-based receivables."""
    return query.filter(Receivable.payment_type == PaymentType.MODULE_BASED)


def filter_receivables_by_team(query: Query, team_id: str) -> Query:
    """Filter receivables by team ID."""
    return query.join(Receivable.bid).filter(Bid.team_id == team_id)


def filter_receivables_by_date_range(query: Query, start_date: date, end_date: date) -> Query:
    """Filter receivables by expected payment date range."""
    return query.filter(
        and_(
            Receivable.expected_payment_date >= start_date,
            Receivable.expected_payment_date <= end_date
        )
    )


def group_receivables_by_client(query: Query) -> Query:
    """Group receivables by client for summary reports."""
    return query.join(Receivable.bid).with_entities(
        Bid.client_name,
        func.count(Receivable.id).label('receivable_count'),
        func.sum(Receivable.contract_value).label('total_value'),
        func.sum(
            case(
                (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                else_=0
            )
        ).label('paid_value'),
        func.count(
            case(
                (Receivable.status == ReceivableStatus.OVERDUE, 1),
                else_=None
            )
        ).label('overdue_count')
    ).group_by(Bid.client_name)


def group_receivables_by_status(query: Query) -> Query:
    """Group receivables by status for analysis."""
    return query.with_entities(
        Receivable.status,
        func.count(Receivable.id).label('receivable_count'),
        func.sum(Receivable.contract_value).label('total_value'),
        func.avg(Receivable.contract_value).label('avg_value')
    ).group_by(Receivable.status)


def group_receivables_by_module(query: Query) -> Query:
    """Group receivables by module for analysis."""
    return query.join(Receivable.module).with_entities(
        ProjectModule.module_name,
        ProjectModule.status.label('module_status'),
        func.count(Receivable.id).label('receivable_count'),
        func.sum(Receivable.contract_value).label('total_value'),
        Receivable.status.label('receivable_status')
    ).group_by(ProjectModule.module_name, ProjectModule.status, Receivable.status)


def group_receivables_by_month(query: Query) -> Query:
    """Group receivables by expected payment month."""
    return query.with_entities(
        func.date_trunc('month', Receivable.expected_payment_date).label('month'),
        func.count(Receivable.id).label('receivable_count'),
        func.sum(Receivable.contract_value).label('expected_value'),
        func.sum(
            case(
                (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                else_=0
            )
        ).label('actual_received')
    ).group_by(func.date_trunc('month', Receivable.expected_payment_date))


def search_receivables_by_text(query: Query, search_term: str) -> Query:
    """Search receivables by text in client name, project title, or module name."""
    search_pattern = f"%{search_term}%"
    
    return query.join(Receivable.bid).join(Receivable.module).filter(
        or_(
            Bid.client_name.ilike(search_pattern),
            Bid.job_title.ilike(search_pattern),
            ProjectModule.module_name.ilike(search_pattern),
            ProjectModule.description.ilike(search_pattern)
        )
    )


def calculate_collection_efficiency(query: Query) -> dict:
    """Calculate collection efficiency metrics."""
    try:
        # Get total and paid amounts
        stats = query.with_entities(
            func.sum(Receivable.contract_value).label('total_value'),
            func.sum(
                case(
                    (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                    else_=0
                )
            ).label('collected_value'),
            func.count(Receivable.id).label('total_count'),
            func.count(
                case(
                    (Receivable.status == ReceivableStatus.PAID, 1),
                    else_=None
                )
            ).label('paid_count')
        ).first()
        
        total_value = float(stats.total_value or 0)
        collected_value = float(stats.collected_value or 0)
        total_count = stats.total_count or 0
        paid_count = stats.paid_count or 0
        
        collection_rate = (collected_value / total_value * 100) if total_value > 0 else 0
        payment_rate = (paid_count / total_count * 100) if total_count > 0 else 0
        
        return {
            'total_value': total_value,
            'collected_value': collected_value,
            'collection_rate': collection_rate,
            'total_count': total_count,
            'paid_count': paid_count,
            'payment_rate': payment_rate,
            'outstanding_value': total_value - collected_value,
            'outstanding_count': total_count - paid_count
        }
        
    except Exception as e:
        logger.error(f"Error calculating collection efficiency: {e}")
        return {}


def get_aging_analysis(query: Query) -> dict:
    """Get aging analysis of receivables."""
    try:
        today = date.today()
        
        # Define aging buckets (days)
        buckets = [
            ('current', 0, 0),           # Due today or future
            ('1-30', 1, 30),             # 1-30 days overdue
            ('31-60', 31, 60),           # 31-60 days overdue
            ('61-90', 61, 90),           # 61-90 days overdue
            ('90+', 91, 999999)          # 90+ days overdue
        ]
        
        aging_data = {}
        
        for bucket_name, min_days, max_days in buckets:
            if bucket_name == 'current':
                # Current and future receivables
                bucket_query = query.filter(
                    or_(
                        Receivable.expected_payment_date >= today,
                        Receivable.status == ReceivableStatus.PAID
                    )
                )
            else:
                # Overdue receivables in specific range
                start_date = today - timedelta(days=max_days)
                end_date = today - timedelta(days=min_days)
                
                bucket_query = query.filter(
                    and_(
                        Receivable.expected_payment_date >= start_date,
                        Receivable.expected_payment_date < end_date,
                        Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL, ReceivableStatus.OVERDUE])
                    )
                )
            
            bucket_stats = bucket_query.with_entities(
                func.count(Receivable.id).label('count'),
                func.sum(Receivable.contract_value).label('value')
            ).first()
            
            aging_data[bucket_name] = {
                'count': bucket_stats.count or 0,
                'value': float(bucket_stats.value or 0)
            }
        
        return aging_data
        
    except Exception as e:
        logger.error(f"Error getting aging analysis: {e}")
        return {}


def validate_receivable_business_rules(db_session, receivable_data: dict) -> dict:
    """Validate business rules for receivable operations."""
    try:
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check if module exists and belongs to bid
        if receivable_data.get('module_id') and receivable_data.get('bid_id'):
            module = db_session.query(ProjectModule).filter(
                ProjectModule.id == receivable_data['module_id'],
                ProjectModule.bid_id == receivable_data['bid_id']
            ).first()
            
            if not module:
                validation_result['is_valid'] = False
                validation_result['errors'].append("Module not found or doesn't belong to this bid")
        
        # Check if receivable already exists for module
        if receivable_data.get('module_id'):
            existing = db_session.query(Receivable).filter(
                Receivable.module_id == receivable_data['module_id']
            ).first()
            
            if existing:
                validation_result['is_valid'] = False
                validation_result['errors'].append("Receivable already exists for this module")
        
        # Check if bid is won
        if receivable_data.get('bid_id'):
            bid = db_session.query(Bid).filter(Bid.id == receivable_data['bid_id']).first()
            if bid and bid.status != 'won':  # Assuming 'won' is the status value
                validation_result['is_valid'] = False
                validation_result['errors'].append("Can only create receivables for won bids")
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Error validating business rules: {e}")
        return {
            'is_valid': False,
            'errors': ['Validation error occurred'],
            'warnings': []
        }