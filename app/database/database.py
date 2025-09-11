from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from redis import Redis
import redis.asyncio as aioredis
from core.config.config import settings
import logging

logger = logging.getLogger(__name__)

def get_database_url():
    """Get the correct database URL for psycopg2."""
    url = settings.DATABASE_URL
    
    # Ensure we're using psycopg2 driver
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    elif "postgresql://" in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://")
    
    # Add SSL mode if not present
    if "sslmode=" not in url:
        connector = "&" if "?" in url else "?"
        url += f"{connector}sslmode=require"
    
    return url

# Create database engine optimized for Supabase Transaction Pooler
DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,        # Required for Supabase transaction pooler mode
    pool_pre_ping=True,        # Test connections before use
    pool_recycle=300,          # Recycle connections every 5 minutes
    echo=settings.DEBUG,       # Enable SQL logging in debug mode
    connect_args={
        "connect_timeout": 10,  # Connection timeout in seconds
        "application_name": "winara_app"  # Helps identify your app in Supabase logs
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData()

# Redis connection with error handling
try:
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    # Test Redis connection
    redis_client.ping()
    logger.info("✅ Redis connection successful")
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}")
    redis_client = None

async def get_redis():
    try:
        redis_conn = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_conn.ping()
        return redis_conn
    except Exception as e:
        logger.warning(f"⚠️ Async Redis connection failed: {e}")
        return None

# Database dependency with proper error handling
def get_db():
    db = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()

# Cache utilities
class CacheKeys:
    USER_SESSION = "user_session:{}"
    ANALYTICS_DASHBOARD = "analytics:dashboard:{}:{}"
    VERTICALS_LIST = "verticals:list"
    TEAM_MEMBERS = "team:members:{}"
    
def get_cache_key(template: str, *args) -> str:
    return template.format(*args)