import re
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import UUID
from core.config.config import settings


def calculate_connect_cost(connects_used: int, boost_connects: int = 0, 
                          connect_rate: float = settings.DEFAULT_CONNECT_COST,
                          boost_rate: float = settings.BOOST_CONNECT_COST) -> Decimal:
    """Calculate total connect cost."""
    regular_cost = Decimal(str(connects_used * connect_rate))
    boost_cost = Decimal(str(boost_connects * boost_rate))
    return regular_cost + boost_cost


def estimate_project_value(budget_type: str, budget_min: Optional[Decimal] = None,
                          budget_max: Optional[Decimal] = None, hourly_rate: Optional[Decimal] = None,
                          estimated_hours: int = 0) -> Optional[Decimal]:
    """Estimate project value based on budget type and parameters."""
    if budget_type == "fixed":
        if budget_min and budget_max:
            return (budget_min + budget_max) / 2
        elif budget_min:
            return budget_min
        elif budget_max:
            return budget_max
    elif budget_type == "hourly" and hourly_rate and estimated_hours > 0:
        return hourly_rate * estimated_hours
    
    return None


def calculate_days_since(date_time: datetime) -> int:
    """Calculate days since a given datetime."""
    return (datetime.utcnow() - date_time).days


def can_edit_bid(created_at: datetime, edit_window_days: int = settings.BID_EDIT_WINDOW_DAYS) -> bool:
    """Check if a bid can still be edited based on creation date."""
    return calculate_days_since(created_at) < edit_window_days


def format_currency(amount: Decimal, currency: str = "USD") -> str:
    """Format currency amount for display."""
    if currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def calculate_win_rate(total_bids: int, wins: int) -> Decimal:
    """Calculate win rate percentage."""
    if total_bids == 0:
        return Decimal('0')
    return Decimal(wins) / Decimal(total_bids) * 100


def calculate_profit_margin(revenue: Decimal, costs: Decimal) -> Decimal:
    """Calculate profit margin percentage."""
    if revenue == 0:
        return Decimal('0')
    return (revenue - costs) / revenue * 100


def generate_slug(text: str) -> str:
    """Generate URL-friendly slug from text."""
    # Convert to lowercase and replace spaces with hyphens
    slug = re.sub(r'[^a-zA-Z0-9\s\-_]', '', text.lower())
    slug = re.sub(r'[\s\-_]+', '-', slug).strip('-')
    return slug


def parse_sort_parameter(sort_param: str) -> tuple[str, str]:
    """Parse sort parameter (e.g., '-created_at' -> ('created_at', 'desc'))."""
    if sort_param.startswith('-'):
        return sort_param[1:], 'desc'
    elif sort_param.startswith('+'):
        return sort_param[1:], 'asc'
    else:
        return sort_param, 'asc'


def build_pagination_cursor(item_id: str, sort_field: str, sort_value: Any) -> str:
    """Build pagination cursor."""
    cursor_data = {
        'id': str(item_id),
        'field': sort_field,
        'value': str(sort_value)
    }
    return json.dumps(cursor_data)


def parse_pagination_cursor(cursor: str) -> Optional[Dict[str, Any]]:
    """Parse pagination cursor."""
    try:
        return json.loads(cursor)
    except (json.JSONDecodeError, TypeError):
        return None


def is_overdue_payment(expected_date: date, actual_date: Optional[date] = None) -> bool:
    """Check if payment is overdue."""
    compare_date = actual_date or date.today()
    return expected_date < compare_date


def calculate_overdue_days(expected_date: date, actual_date: Optional[date] = None) -> int:
    """Calculate days overdue."""
    compare_date = actual_date or date.today()
    if expected_date >= compare_date:
        return 0
    return (compare_date - expected_date).days


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    # Limit length
    sanitized = sanitized[-255:] if len(sanitized) > 255 else sanitized
    return sanitized


def calculate_roi(revenue: Decimal, investment: Decimal) -> Decimal:
    """Calculate Return on Investment."""
    if investment == 0:
        return Decimal('0')
    return (revenue - investment) / investment * 100


def get_date_range_for_period(period: str, custom_start: Optional[date] = None, 
                             custom_end: Optional[date] = None) -> tuple[date, date]:
    """Get date range for a given period."""
    today = date.today()
    
    if period == "day":
        return today, today
    elif period == "week":
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)  # Sunday
        return start, end
    elif period == "month":
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return start, end
    elif period == "custom" and custom_start and custom_end:
        return custom_start, custom_end
    else:
        # Default to current month
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return start, end


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data showing only last few characters."""
    if len(data) <= visible_chars:
        return '*' * len(data)
    return '*' * (len(data) - visible_chars) + data[-visible_chars:]


def calculate_performance_score(wins: int, total_bids: int, revenue: Decimal, 
                               connect_cost: Decimal) -> Decimal:
    """Calculate overall performance score (0-100)."""
    if total_bids == 0:
        return Decimal('0')
    
    win_rate = Decimal(wins) / Decimal(total_bids)
    roi = calculate_roi(revenue, connect_cost) / 100 if connect_cost > 0 else Decimal('0')
    
    # Weighted score: 60% win rate, 40% ROI
    score = (win_rate * 60) + (min(roi, Decimal('1')) * 40)
    return min(score * 100, Decimal('100'))