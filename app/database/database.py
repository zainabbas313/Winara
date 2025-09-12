# database.py
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from redis import Redis
import redis.asyncio as aioredis
from core.config.config import settings
import logging
import os

logger = logging.getLogger(__name__)

def get_database_url():
    """Get the correct database URL based on environment."""
    url = settings.DATABASE_URL
    
    # Check if we're in production (Render sets this environment variable)
    is_production = os.getenv('RENDER_SERVICE_NAME') is not None
    
    if is_production:
        logger.info("🏭 Production environment detected (Render)")
        # For production on Render, convert pooler to direct connection if needed
        if "pooler.supabase.com:6543" in url:
            # Use the session pooler (port 5432) instead of transaction pooler (port 6543)
            # This is more reliable for production deployments
            url = url.replace("aws-1-ap-southeast-1.pooler.supabase.com:6543", "aws-1-ap-southeast-1.pooler.supabase.com:5432")
            logger.info("🔄 Switched from transaction pooler to session pooler for production")
    else:
        logger.info("🏠 Local development environment detected")
        # For local development, keep the working pooler connection
        # Since you confirmed pooler works locally, we'll use that
    
    # Ensure we're using psycopg2 driver
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    elif "postgresql://" in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://")
    
    # Ensure SSL mode is set
    if "sslmode=" not in url:
        connector = "&" if "?" in url else "?"
        url += f"{connector}sslmode=require"
    
    # Log the connection details (without password)
    try:
        if '@' in url:
            before_at = url.split('@')[0]
            after_at = url.split('@')[1]
            masked_before = before_at.split(':')[:-1] if ':' in before_at else [before_at]
            logger.info(f"🔗 Database URL: {':'.join(masked_before)}:***@{after_at}")
        else:
            logger.info("🔗 Database URL configured")
    except:
        logger.info("🔗 Database URL configured (parsing failed)")
    
    return url

# Create database engine configuration
DATABASE_URL = get_database_url()
is_production = os.getenv('RENDER_SERVICE_NAME') is not None

if is_production:
    # Production configuration (Render)
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,        # Use connection pooling for session pooler
        pool_size=3,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=30,
        echo=False,
        connect_args={
            "connect_timeout": 20,
            "application_name": "winara_app_prod"
        }
    )
else:
    # Local development configuration
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,         # Use NullPool for transaction pooler (local dev)
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.DEBUG if hasattr(settings, 'DEBUG') else False,
        connect_args={
            "connect_timeout": 10,
            "application_name": "winara_app_dev"
        }
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

# Redis connection - don't fail on local development
redis_client = None
try:
    if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    else:
        logger.info("ℹ️ No Redis URL configured")
except Exception as e:
    if is_production:
        logger.error(f"❌ Redis connection failed in production: {e}")
    else:
        logger.info(f"ℹ️ Redis not available locally (this is fine for development): {e}")
    redis_client = None

async def get_redis():
    try:
        if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
            redis_conn = await aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                retry_on_timeout=True
            )
            await redis_conn.ping()
            return redis_conn
        return None
    except Exception as e:
        logger.warning(f"⚠️ Async Redis connection failed: {e}")
        return None

# Database dependency
def get_db():
    db = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        if db:
            try:
                db.rollback()
            except:
                pass
        raise
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# Test database connection - don't crash on failure
def test_database_connection(max_retries=3):
    """Test the database connection"""
    for attempt in range(max_retries):
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT NOW() as current_time")).fetchone()
                logger.info(f"✅ Database connection successful: {result[0]}")
                return True
        except Exception as e:
            logger.error(f"❌ Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(1)  # Short delay between retries
    
    logger.error("❌ Database connection failed after all attempts")
    return False

# Health check function
def get_database_health():
    """Get database health status"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": f"error: {str(e)}"}

# Cache utilities
class CacheKeys:
    USER_SESSION = "user_session:{}"
    ANALYTICS_DASHBOARD = "analytics:dashboard:{}:{}"
    VERTICALS_LIST = "verticals:list"
    TEAM_MEMBERS = "team:members:{}"
    
def get_cache_key(template: str, *args) -> str:
    return template.format(*args)

logger.info("🚀 Database module loaded successfully")