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