from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Upwork Bidders Management"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:zain@localhost/bidder"
    DATABASE_TEST_URL: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 300000
    REFRESH_TOKEN_EXPIRE_DAYS: int = 2
    
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = ""
    EMAILS_FROM_NAME: str = "Upwork Bidders Management"
    
    # File Upload
    UPLOAD_FOLDER: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx"}
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Analytics
    CACHE_ANALYTICS_MINUTES: int = 15
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Default timezone
    DEFAULT_TIMEZONE: str = "UTC+05:00"
    
    # Connect costs (can be made configurable per vertical)
    DEFAULT_CONNECT_COST: float = 0.15
    BOOST_CONNECT_COST: float = 0.15
    
    # Business rules
    BID_EDIT_WINDOW_DAYS: int = 5

    # Cache settings
    REDIS_URL: Optional[str] = Field(
        default=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        description="Redis connection URL for caching"
    )
    CACHE_TTL_MINUTES: int = Field(
        default=15,
        description="Default cache TTL in minutes"
    )
    CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable/disable caching"
    )
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable/disable rate limiting"
    )
    DEFAULT_RATE_LIMIT: int = Field(
        default=100,
        description="Default rate limit per hour"
    )
    
    # Export settings
    MAX_EXPORT_SIZE_MB: int = Field(
        default=50,
        description="Maximum export file size in MB"
    )
    EXPORT_CLEANUP_HOURS: int = Field(
        default=24,
        description="Hours after which export files are cleaned up"
    )
    EXPORT_DIRECTORY: str = Field(
        default="/data",
        description="Directory for temporary export files"
    )
    
    # Analytics thresholds
    WIN_RATE_BENCHMARK: float = Field(
        default=15.0,
        description="Industry benchmark for win rate percentage"
    )
    COST_PER_WIN_THRESHOLD: float = Field(
        default=50.0,
        description="Threshold for high cost per win alert"
    )
    ROI_THRESHOLD: float = Field(
        default=100.0,
        description="Minimum acceptable ROI percentage"
    )
    
    # Performance settings
    MAX_CHART_DATA_POINTS: int = Field(
        default=365,
        description="Maximum data points in chart responses"
    )
    QUERY_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Database query timeout"
    )
    
    # Security settings
    AUDIT_ENABLED: bool = Field(
        default=True,
        description="Enable audit logging"
    )
    SENSITIVE_DATA_MASKING: bool = Field(
        default=True,
        description="Mask sensitive data in logs"
    )
    
    # ML/AI settings (for future use)
    ENABLE_PREDICTIVE_ANALYTICS: bool = Field(
        default=True,
        description="Enable predictive analytics features"
    )
    MODEL_CONFIDENCE_THRESHOLD: float = Field(
        default=0.7,
        description="Minimum confidence for ML predictions"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()