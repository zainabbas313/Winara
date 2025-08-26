"""
Data formatting utilities for analytics output.
"""

from typing import Any, Dict, List
from decimal import Decimal, InvalidOperation
from datetime import date, datetime


def format_currency(value: Any, currency: str = "USD") -> str:
    """Format monetary values for display."""
    if value is None:
        return f"${0:.2f}"
    
    try:
        decimal_value = Decimal(str(value))
        return f"${decimal_value:.2f}"
    except (InvalidOperation, ValueError):
        return f"${0:.2f}"


def format_percentage(value: Any, decimal_places: int = 1) -> str:
    """Format percentage values for display."""
    if value is None:
        return f"{0:.{decimal_places}f}%"
    
    try:
        decimal_value = Decimal(str(value))
        return f"{decimal_value:.{decimal_places}f}%"
    except (InvalidOperation, ValueError):
        return f"{0:.{decimal_places}f}%"


def format_large_number(value: Any) -> str:
    """Format large numbers with appropriate suffixes (K, M, B)."""
    if value is None:
        return "0"
    
    try:
        num = float(value)
        
        if abs(num) >= 1_000_000_000:
            return f"{num / 1_000_000_000:.1f}B"
        elif abs(num) >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif abs(num) >= 1_000:
            return f"{num / 1_000:.1f}K"
        else:
            return f"{num:.0f}"
    except (ValueError, TypeError):
        return "0"


def format_analytics_summary(data: Dict[str, Any]) -> Dict[str, str]:
    """Format analytics summary data for display."""
    formatted = {}
    
    for key, value in data.items():
        if key in ['revenue', 'connect_spend', 'total_cost']:
            formatted[key] = format_currency(value)
        elif key in ['win_rate', 'profit_margin']:
            formatted[key] = format_percentage(value)
        elif key in ['total_bids', 'wins']:
            formatted[key] = format_large_number(value)
        else:
            formatted[key] = str(value) if value is not None else "N/A"
    
    return formatted