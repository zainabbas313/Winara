"""
Custom exception classes for the analytics system.
"""

class AnalyticsError(Exception):
    """Base exception for analytics-related errors."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AnalyticsError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: str = None, value=None):
        self.field = field
        self.value = value
        super().__init__(message, "VALIDATION_ERROR", {
            "field": field,
            "value": str(value) if value is not None else None
        })


class PermissionError(AnalyticsError):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str, required_role: str = None, user_role: str = None):
        self.required_role = required_role
        self.user_role = user_role
        super().__init__(message, "PERMISSION_DENIED", {
            "required_role": required_role,
            "user_role": user_role
        })


class DataNotFoundError(AnalyticsError):
    """Raised when requested data is not found."""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(message, "DATA_NOT_FOUND", {
            "resource_type": resource_type,
            "resource_id": resource_id
        })


class CacheError(AnalyticsError):
    """Raised when caching operations fail."""
    
    def __init__(self, message: str, operation: str = None):
        self.operation = operation
        super().__init__(message, "CACHE_ERROR", {"operation": operation})


class ExportError(AnalyticsError):
    """Raised when data export operations fail."""
    
    def __init__(self, message: str, export_format: str = None, file_size: int = None):
        self.export_format = export_format
        self.file_size = file_size
        super().__init__(message, "EXPORT_ERROR", {
            "format": export_format,
            "file_size": file_size
        })


class RateLimitError(AnalyticsError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str, limit: int = None, window: int = None, retry_after: int = None):
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        super().__init__(message, "RATE_LIMIT_EXCEEDED", {
            "limit": limit,
            "window": window,
            "retry_after": retry_after
        })
