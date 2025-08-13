import hashlib
import hmac
import secrets
import re
from typing import Optional
from datetime import datetime
from user_agents import parse


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def hash_sensitive_data(data: str, salt: Optional[str] = None) -> tuple:
    """Hash sensitive data with salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    
    hashed = hashlib.pbkdf2_hmac('sha256', data.encode('utf-8'), salt.encode('utf-8'), 100000)
    return hashed.hex(), salt


def verify_sensitive_data(data: str, hashed: str, salt: str) -> bool:
    """Verify sensitive data against hash."""
    new_hash, _ = hash_sensitive_data(data, salt)
    return hmac.compare_digest(new_hash, hashed)


def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent XSS and other attacks."""
    if not input_string:
        return ""
    
    # Remove null bytes
    sanitized = input_string.replace('\x00', '')
    
    # Limit length
    sanitized = sanitized[:max_length]
    
    # Remove potentially dangerous characters for SQL injection (basic)
    dangerous_chars = ['"', "'", ';', '--', '/*', '*/', 'xp_', 'sp_']
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    return sanitized.strip()


def validate_password_strength(password: str) -> tuple[bool, list]:
    """Validate password strength and return status with error messages."""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if len(password) > 128:
        errors.append("Password must be less than 128 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")
    
    # Check for common passwords (basic check)
    common_passwords = [
        'password', '123456', '123456789', 'qwerty', 'abc123',
        'password123', 'admin', 'letmein', 'welcome', 'monkey'
    ]
    
    if password.lower() in common_passwords:
        errors.append("Password is too common")
    
    return len(errors) == 0, errors


def parse_user_agent(user_agent_string: str) -> dict:
    """Parse user agent string to extract device information."""
    try:
        user_agent = parse(user_agent_string)
        
        return {
            'os': f"{user_agent.os.family} {user_agent.os.version_string}",
            'browser': user_agent.browser.family,
            'browser_version': user_agent.browser.version_string,
            'device_type': 'mobile' if user_agent.is_mobile else 'tablet' if user_agent.is_tablet else 'desktop'
        }
    except Exception:
        return {
            'os': 'Unknown',
            'browser': 'Unknown',
            'browser_version': 'Unknown',
            'device_type': 'desktop'
        }


def detect_suspicious_activity(login_attempts: list, time_window_minutes: int = 15) -> bool:
    """Detect suspicious login activity."""
    if len(login_attempts) < 5:
        return False
    
    # Check for too many attempts in a short time
    recent_attempts = [
        attempt for attempt in login_attempts 
        if (datetime.utcnow() - attempt['timestamp']).total_seconds() < time_window_minutes * 60
    ]
    
    if len(recent_attempts) >= 5:
        return True
    
    # Check for attempts from multiple IPs
    unique_ips = set(attempt['ip_address'] for attempt in recent_attempts)
    if len(unique_ips) >= 3:
        return True
    
    return False


def calculate_risk_score(factors: dict) -> int:
    """Calculate risk score based on various factors (1-5 scale)."""
    score = 1
    
    # IP-based factors
    if factors.get('new_ip', False):
        score += 1
    
    if factors.get('different_country', False):
        score += 2
    
    # Time-based factors
    if factors.get('unusual_time', False):
        score += 1
    
    # Device factors
    if factors.get('new_device', False):
        score += 1
    
    # Behavior factors
    if factors.get('failed_attempts', 0) > 3:
        score += 2
    
    return min(score, 5)