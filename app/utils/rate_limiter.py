"""
Rate limiting utilities for API endpoints.
"""

import time
from typing import Dict, Optional
from functools import wraps
from fastapi import HTTPException, status, Request
import redis
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# In-memory fallback when Redis is not available
_memory_store: Dict[str, Dict[str, any]] = {}

class RateLimiter:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.use_redis = redis_client is not None
        
    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, dict]:
        """
        Check if request is allowed based on rate limits.
        
        Args:
            key: Unique identifier for the rate limit (e.g., user_id:endpoint)
            limit: Maximum number of requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = int(time.time())
        
        if self.use_redis:
            return self._check_redis_rate_limit(key, limit, window, now)
        else:
            return self._check_memory_rate_limit(key, limit, window, now)
    
    def _check_redis_rate_limit(self, key: str, limit: int, window: int, now: int) -> tuple[bool, dict]:
        """Check rate limit using Redis."""
        try:
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window)
            results = pipe.execute()
            
            current_requests = results[1]
            
            rate_limit_info = {
                "limit": limit,
                "remaining": max(0, limit - current_requests - 1),
                "reset_time": now + window,
                "window": window
            }
            
            if current_requests < limit:
                return True, rate_limit_info
            else:
                # Remove the request we just added since we're over the limit
                self.redis_client.zrem(key, str(now))
                rate_limit_info["remaining"] = 0
                return False, rate_limit_info
                
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fallback to allowing the request if Redis fails
            return True, {"limit": limit, "remaining": limit - 1, "reset_time": now + window, "window": window}
    
    def _check_memory_rate_limit(self, key: str, limit: int, window: int, now: int) -> tuple[bool, dict]:
        """Check rate limit using in-memory storage."""
        if key not in _memory_store:
            _memory_store[key] = {"requests": [], "reset_time": now + window}
        
        # Clean old requests
        store = _memory_store[key]
        store["requests"] = [req_time for req_time in store["requests"] if req_time > now - window]
        
        current_requests = len(store["requests"])
        
        rate_limit_info = {
            "limit": limit,
            "remaining": max(0, limit - current_requests - 1),
            "reset_time": store["reset_time"],
            "window": window
        }
        
        if current_requests < limit:
            store["requests"].append(now)
            return True, rate_limit_info
        else:
            rate_limit_info["remaining"] = 0
            return False, rate_limit_info


# Global rate limiter instance
_rate_limiter = RateLimiter()

def set_rate_limiter(redis_client: Optional[redis.Redis] = None):
    """Set the global rate limiter instance."""
    global _rate_limiter
    _rate_limiter = RateLimiter(redis_client)


def rate_limit(calls: int, period: int):
    """
    Decorator for rate limiting API endpoints.
    
    Args:
        calls: Number of calls allowed
        period: Time period in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user info from the request
            current_user = None
            request = None
            
            for arg in args + tuple(kwargs.values()):
                if hasattr(arg, 'id') and hasattr(arg, 'role'):  # User object
                    current_user = arg
                elif hasattr(arg, 'client'):  # Request object
                    request = arg
            
            if current_user:
                # Create rate limit key
                endpoint = func.__name__
                key = f"rate_limit:{current_user.id}:{endpoint}"
                
                # Check rate limit
                is_allowed, rate_info = _rate_limiter.is_allowed(key, calls, period)
                
                if not is_allowed:
                    logger.warning(f"Rate limit exceeded for user {current_user.id} on {endpoint}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. {calls} calls per {period} seconds allowed.",
                        headers={
                            "X-RateLimit-Limit": str(rate_info["limit"]),
                            "X-RateLimit-Remaining": str(rate_info["remaining"]),
                            "X-RateLimit-Reset": str(rate_info["reset_time"]),
                            "Retry-After": str(period)
                        }
                    )
                
                # Add rate limit headers to response (this would need middleware support)
                response = await func(*args, **kwargs)
                
                # If response has headers attribute, add rate limit info
                if hasattr(response, 'headers'):
                    response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
                    response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
                    response.headers["X-RateLimit-Reset"] = str(rate_info["reset_time"])
                
                return response
            else:
                # If no user found, proceed without rate limiting
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

