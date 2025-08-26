"""
Validation utilities for analytics data and requests.
"""

from typing import Any, Dict, Optional, List
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal, InvalidOperation

from validators import ValidationError
import re
from typing import Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from uuid import UUID
import validators


def validate_email(email: str) -> bool:
    """Validate email format."""
    return validators.email(email)


def validate_url(url: str) -> bool:
    """Validate URL format."""
    return validators.url(url)


def validate_phone(phone: str) -> bool:
    """Validate phone number format (international)."""
    # Basic international phone number validation
    pattern = r'^[\+]?[1-9][\d]{0,15}$'
    return bool(re.match(pattern, phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')))


def validate_currency_code(code: str) -> bool:
    """Validate ISO currency code."""
    # ISO 4217 currency codes are 3 uppercase letters
    pattern = r'^[A-Z]{3}$'
    return bool(re.match(pattern, code))


def validate_decimal(value: str, max_digits: int = 12, decimal_places: int = 2) -> tuple[bool, Optional[Decimal]]:
    """Validate and convert decimal value."""
    try:
        decimal_value = Decimal(str(value))
        
        # Check if it has too many decimal places
        if decimal_value.as_tuple().exponent < -decimal_places:
            return False, None
        
        # Check total digits
        sign, digits, exponent = decimal_value.as_tuple()
        if len(digits) > max_digits:
            return False, None
        
        return True, decimal_value
    except (InvalidOperation, ValueError):
        return False, None


def validate_slug(slug: str) -> bool:
    """Validate slug format (URL-safe string)."""
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    return bool(re.match(pattern, slug))


def validate_username(username: str) -> tuple[bool, list]:
    """Validate username format and return errors if any."""
    errors = []
    
    if not username:
        errors.append("Username is required")
        return False, errors
    
    if len(username) < 3:
        errors.append("Username must be at least 3 characters long")
    
    if len(username) > 50:
        errors.append("Username must be less than 50 characters long")
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        errors.append("Username can only contain letters, numbers, underscores, and hyphens")
    
    if username.startswith(('_', '-')) or username.endswith(('_', '-')):
        errors.append("Username cannot start or end with underscore or hyphen")
    
    # Reserved usernames
    reserved = ['admin', 'administrator', 'root', 'api', 'www', 'mail', 'support', 'null', 'undefined']
    if username.lower() in reserved:
        errors.append("Username is reserved")
    
    return len(errors) == 0, errors


def validate_date_range(start_date: date, end_date: date) -> tuple[bool, Optional[str]]:
    """Validate date range."""
    if start_date > end_date:
        return False, "Start date must be before end date"
    
    # Check if range is reasonable (not more than 10 years)
    if (end_date - start_date).days > 3650:
        return False, "Date range cannot exceed 10 years"
    
    return True, None


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Validate file extension."""
    if not filename:
        return False
    
    # Get file extension
    extension = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
    return extension in allowed_extensions


def validate_connects_usage(connects_used: int, boost_connects: int = 0) -> tuple[bool, Optional[str]]:
    """Validate connects usage for bids."""
    total_connects = connects_used + boost_connects
    
    if connects_used < 1:
        return False, "At least 1 connect is required"
    
    if connects_used > 50:
        return False, "Cannot use more than 50 regular connects"
    
    if boost_connects < 0:
        return False, "Boost connects cannot be negative"
    
    if boost_connects > 50:
        return False, "Cannot use more than 50 boost connects"
    
    if total_connects > 100:
        return False, "Total connects cannot exceed 100"
    
    return True, None


def validate_budget_consistency(budget_type: str, budget_min: Optional[Decimal], 
                              budget_max: Optional[Decimal], hourly_rate: Optional[Decimal]) -> tuple[bool, list]:
    """Validate budget field consistency."""
    errors = []
    
    if budget_type == "fixed":
        if budget_min is None:
            errors.append("Minimum budget is required for fixed budget type")
        elif budget_min <= 0:
            errors.append("Minimum budget must be greater than 0")
        
        if budget_max is not None and budget_min is not None:
            if budget_max < budget_min:
                errors.append("Maximum budget must be greater than or equal to minimum budget")
    
    elif budget_type == "hourly":
        if hourly_rate is None:
            errors.append("Hourly rate is required for hourly budget type")
        elif hourly_rate <= 0:
            errors.append("Hourly rate must be greater than 0")
        elif hourly_rate > 1000:
            errors.append("Hourly rate seems unreasonably high")
    
    return len(errors) == 0, errors


def validate_timezone(timezone: str) -> bool:
    """Validate timezone format."""
    # Basic timezone validation - should be improved with pytz in production
    pattern = r'^UTC[+-]\d{2}:\d{2}$|^UTC$'
    return bool(re.match(pattern, timezone))

def validate_uuid(value: Any, field_name: str = "UUID") -> UUID:
    """Validate and convert UUID string to UUID object."""
    if value is None:
        return None
    
    if isinstance(value, UUID):
        return value
    
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            raise ValidationError(f"Invalid {field_name} format", field=field_name, value=value)
    
    raise ValidationError(f"{field_name} must be a valid UUID string", field=field_name, value=value)


def validate_date_range(date_from: Optional[date], date_to: Optional[date]) -> None:
    """Validate date range parameters."""
    if date_from and date_to:
        if date_from > date_to:
            raise ValidationError("Start date cannot be after end date")
        
        # Check if date range is too large (e.g., more than 1 year)
        if (date_to - date_from).days > 365:
            raise ValidationError("Date range cannot exceed 365 days")
    
    # Check if dates are not in the future
    today = date.today()
    if date_from and date_from > today:
        raise ValidationError("Start date cannot be in the future")
    if date_to and date_to > today:
        raise ValidationError("End date cannot be in the future")


def validate_pagination_params(page: int, limit: int) -> None:
    """Validate pagination parameters."""
    if page < 1:
        raise ValidationError("Page number must be greater than 0", field="page", value=page)
    
    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100", field="limit", value=limit)


def validate_decimal(value: Any, field_name: str, min_value: Optional[Decimal] = None, 
                    max_value: Optional[Decimal] = None) -> Decimal:
    """Validate and convert decimal values."""
    if value is None:
        return None
    
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, (int, float)):
        decimal_value = Decimal(str(value))
    elif isinstance(value, str):
        try:
            decimal_value = Decimal(value)
        except (InvalidOperation, ValueError):
            raise ValidationError(f"Invalid {field_name} format", field=field_name, value=value)
    else:
        raise ValidationError(f"{field_name} must be a number", field=field_name, value=value)
    
    if min_value is not None and decimal_value < min_value:
        raise ValidationError(f"{field_name} must be >= {min_value}", field=field_name, value=value)
    
    if max_value is not None and decimal_value > max_value:
        raise ValidationError(f"{field_name} must be <= {max_value}", field=field_name, value=value)
    
    return decimal_value


def sanitize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize and validate filter parameters."""
    if not filters:
        return {}
    
    sanitized = {}
    
    # Validate team_id
    if 'team_id' in filters:
        sanitized['team_id'] = validate_uuid(filters['team_id'], 'team_id')
    
    # Validate user_id
    if 'user_id' in filters:
        sanitized['user_id'] = validate_uuid(filters['user_id'], 'user_id')
    
    # Validate dates
    date_from = None
    date_to = None
    
    if 'date_from' in filters:
        date_str = filters['date_from']
        if isinstance(date_str, str):
            try:
                date_from = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                sanitized['date_from'] = date_from
            except ValueError:
                raise ValidationError("Invalid date_from format")
    
    if 'date_to' in filters:
        date_str = filters['date_to']
        if isinstance(date_str, str):
            try:
                date_to = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                sanitized['date_to'] = date_to
            except ValueError:
                raise ValidationError("Invalid date_to format")
    
    # Validate date range
    validate_date_range(date_from, date_to)
    
    # Validate scope
    if 'scope' in filters:
        scope = filters['scope']
        if scope not in ['admin', 'team', 'member']:
            raise ValidationError("Invalid scope value", field='scope', value=scope)
        sanitized['scope'] = scope
    
    return sanitized