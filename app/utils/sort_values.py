
from schemas.bid import BidListFilter, BidSortField, EnhancedBidFilter, SortDirection
from models.models import Bid, Team, User
from sqlalchemy import asc, desc, or_
from models.models import User 
from fastapi import HTTPException
from models.models import Receivable
from schemas.receivable import ReceivableListFilter


def _apply_sorting(query, sort_by: str, instance):
    """Apply sorting to a query using the User table."""
    sort_field, direction = parse_sort_parameter(sort_by)

    # Whitelist allowed sort fields from User model
    if instance == User:
        allowed_fields = {
            "created_at": User.created_at,
            "updated_at": User.updated_at,
            "email": User.email,
            "first_name": User.first_name,
            "last_name": User.last_name,
            "status": User.status,
            "role": User.role
        }
    if instance == Team:
        allowed_fields = {
            "created_at": Team.created_at,
            "updated_at": Team.updated_at,
            "name": Team.name,
            "status": Team.status
        }


    column = allowed_fields.get(sort_field)
    if column is None:
        raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_field}")

    return query.order_by(desc(column) if direction == 'desc' else asc(column))

def parse_sort_parameter(sort_by: str):
    """
    Parse sort string like '-created_at' or 'email' into (field_name, direction).
    direction is 'asc' or 'desc'.
    """
    if not sort_by:
        return "created_at", "desc"  # default
    sort_by = sort_by.strip()
    if sort_by.startswith("-"):
        return sort_by[1:], "desc"
    elif sort_by.startswith("+"):
        return sort_by[1:], "asc"
    else:
        return sort_by, "asc"


def _apply_sorting_bid(query, sort_by: str, instance):
    """Apply sorting to a query based on the model instance."""
    sort_field, direction = parse_sort_parameter(sort_by)

    # Get allowed fields based on instance type
    allowed_fields = _get_allowed_fields(instance)
    
    column = allowed_fields.get(sort_field)
    if column is None:
        raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_field}")

    return query.order_by(desc(column) if direction == 'desc' else asc(column))


def _get_allowed_fields(instance):
    """Get allowed sort fields for different model instances."""
    if instance == User:
        return {
            "created_at": User.created_at,
            "updated_at": User.updated_at,
            "email": User.email,
            "first_name": User.first_name,
            "last_name": User.last_name,
            "status": User.status,
            "role": User.role
        }
    elif instance == Team:
        return {
            "created_at": Team.created_at,
            "updated_at": Team.updated_at,
            "name": Team.name,
            "status": Team.status
        }
    elif instance == Bid:
        return {
            "created_at": Bid.created_at,
            "updated_at": Bid.updated_at,
            "submitted_at": Bid.submitted_at,
            "job_title": Bid.job_title,
            "status": Bid.status,
            "connects_used": Bid.connects_used,
            "total_cost": Bid.total_cost,
            "budget_type": Bid.budget_type,
            "last_status_change": Bid.last_status_change
        }
    else:
        return {}


def parse_sort_parameter(sort_by: str):
    """
    Parse sort string like '-created_at' or 'email' into (field_name, direction).
    direction is 'asc' or 'desc'.
    """
    if not sort_by:
        return "created_at", "desc"  # default
    sort_by = sort_by.strip()
    if sort_by.startswith("-"):
        return sort_by[1:], "desc"
    elif sort_by.startswith("+"):
        return sort_by[1:], "asc"
    else:
        return sort_by, "asc"


def _apply_bid_filters(query, filters: BidListFilter):
    """Apply bid-specific filters to query."""
    if filters.status:
        query = query.filter(Bid.status == filters.status)
    if filters.team_id:
        query = query.filter(Bid.team_id == filters.team_id)
    if filters.member_id:
        query = query.filter(Bid.member_id == filters.member_id)
    if filters.vertical_id:
        query = query.filter(Bid.vertical_id == filters.vertical_id)
    if filters.budget_type:
        query = query.filter(Bid.budget_type == filters.budget_type)
    if filters.date_from:
        query = query.filter(Bid.submitted_at >= filters.date_from)
    if filters.date_to:
        query = query.filter(Bid.submitted_at <= filters.date_to)
    if filters.q:
        search_term = f"%{filters.q}%"
        query = query.filter(
            or_(
                Bid.job_title.ilike(search_term),
                Bid.client_name.ilike(search_term),
                Bid.proposal_text.ilike(search_term)
            )
        )
    return query


def _apply_enhanced_filters(query, filters: EnhancedBidFilter):
    """Apply enhanced filters to query."""
    query = _apply_bid_filters(query, filters)
    
    if filters.min_connect_cost:
        query = query.filter(Bid.connect_cost >= filters.min_connect_cost)
    if filters.max_connect_cost:
        query = query.filter(Bid.connect_cost <= filters.max_connect_cost)
    if filters.competition_level:
        query = query.filter(Bid.competition_level == filters.competition_level)
    if filters.is_featured is not None:
        query = query.filter(Bid.is_featured == filters.is_featured)
    
    return query


def _apply_enhanced_sorting(query, sort_field: BidSortField, sort_direction: SortDirection):
    """Apply enhanced sorting to query."""
    if sort_field == BidSortField.SUBMITTED_AT:
        order_func = desc if sort_direction == SortDirection.DESC else asc
        query = query.order_by(order_func(Bid.submitted_at))
    elif sort_field == BidSortField.TOTAL_COST:
        order_func = desc if sort_direction == SortDirection.DESC else asc
        query = query.order_by(order_func(Bid.total_cost))
    elif sort_field == BidSortField.CONNECTS_USED:
        order_func = desc if sort_direction == SortDirection.DESC else asc
        query = query.order_by(order_func(Bid.connects_used))
    elif sort_field == BidSortField.STATUS:
        order_func = desc if sort_direction == SortDirection.DESC else asc
        query = query.order_by(order_func(Bid.status))
    
    return query


def _apply_sorting_receivable(query, sort_by: str, instance):
    """Apply sorting to a receivable query based on the model instance."""
    sort_field, direction = parse_sort_parameter(sort_by)

    # Get allowed fields for receivables
    allowed_fields = _get_allowed_fields_receivable(instance)
    
    column = allowed_fields.get(sort_field)
    if column is None:
        raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_field}")

    return query.order_by(desc(column) if direction == 'desc' else asc(column))


def _get_allowed_fields_receivable(instance):
    """Get allowed sort fields for receivable model."""
    if instance == Receivable:
        return {
            "created_at": Receivable.created_at,
            "updated_at": Receivable.updated_at,
            "expected_payment_date": Receivable.expected_payment_date,
            "actual_payment_date": Receivable.actual_payment_date,
            "contract_value": Receivable.contract_value,
            "payment_amount": Receivable.payment_amount,
            "status": Receivable.status,
            "client_name": Receivable.client_name,
            "project_title": Receivable.project_title,
            "currency": Receivable.currency
        }
    else:
        return {}


def _apply_receivable_filters(query, filters: ReceivableListFilter):
    """Apply receivable-specific filters to query."""
    if filters.team_id:
        query = query.filter(Receivable.team_id == filters.team_id)
    
    if filters.status:
        query = query.filter(Receivable.status == filters.status)
    
    if filters.date_from:
        query = query.filter(Receivable.expected_payment_date >= filters.date_from)
    
    if filters.date_to:
        query = query.filter(Receivable.expected_payment_date <= filters.date_to)
    
    if filters.client_name:
        search_term = f"%{filters.client_name}%"
        query = query.filter(Receivable.client_name.ilike(search_term))
    
    return query


# Update the existing _get_allowed_fields function to include Receivable
def _get_allowed_fields_updated(instance):
    """Get allowed sort fields for different model instances (updated version)."""
    if instance == User:
        return {
            "created_at": User.created_at,
            "updated_at": User.updated_at,
            "email": User.email,
            "first_name": User.first_name,
            "last_name": User.last_name,
            "status": User.status,
            "role": User.role
        }
    elif instance == Team:
        return {
            "created_at": Team.created_at,
            "updated_at": Team.updated_at,
            "name": Team.name,
            "status": Team.status
        }
    elif instance == Bid:
        return {
            "created_at": Bid.created_at,
            "updated_at": Bid.updated_at,
            "submitted_at": Bid.submitted_at,
            "job_title": Bid.job_title,
            "status": Bid.status,
            "connects_used": Bid.connects_used,
            "total_cost": Bid.total_cost,
            "budget_type": Bid.budget_type,
            "last_status_change": Bid.last_status_change
        }
    elif instance == Receivable:
        return {
            "created_at": Receivable.created_at,
            "updated_at": Receivable.updated_at,
            "expected_payment_date": Receivable.expected_payment_date,
            "actual_payment_date": Receivable.actual_payment_date,
            "contract_value": Receivable.contract_value,
            "payment_amount": Receivable.payment_amount,
            "status": Receivable.status,
            "client_name": Receivable.client_name,
            "project_title": Receivable.project_title,
            "currency": Receivable.currency
        }
    else:
        return {}


# Generic sorting function that works with all models
def _apply_sorting_generic(query, sort_by: str, instance):
    """Generic apply sorting function that works with all model instances."""
    sort_field, direction = parse_sort_parameter(sort_by)

    # Get allowed fields based on instance type
    allowed_fields = _get_allowed_fields_updated(instance)
    
    column = allowed_fields.get(sort_field)
    if column is None:
        # Fallback to created_at if field doesn't exist
        column = getattr(instance, 'created_at', None)
        if column is None:
            raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_field}")

    return query.order_by(desc(column) if direction == 'desc' else asc(column))