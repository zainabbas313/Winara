from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from redis import Redis
import redis.asyncio as aioredis
from core.config.config import settings
import logging
import os

logger = logging.getLogger(__name__)

def get_database_url():
    """Get the correct database URL for production deployment."""
    url = settings.DATABASE_URL
    
    # For production on Render, use direct connection instead of pooler
    # Replace pooler URL with direct connection URL
    if "pooler.supabase.com:6543" in url:
        # Convert from pooler to direct connection
        url = url.replace("aws-1-ap-southeast-1.pooler.supabase.com:6543", "db.hhhutpdjaozsyifglpmo.supabase.co:5432")
        logger.info("Converted pooler URL to direct connection for production")
    
    # Ensure we're using psycopg2 driver
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    elif "postgresql://" in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://")
    
    # Add SSL mode if not present
    if "sslmode=" not in url:
        connector = "&" if "?" in url else "?"
        url += f"{connector}sslmode=require"
    
    # Log the connection type (without password)
    masked_url = url.split('@')[0].split(':')[:-1]
    logger.info(f"Database connection configured: {':'.join(masked_url)}:***@{url.split('@')[1]}")
    
    return url

# Create database engine optimized for Render deployment
DATABASE_URL = get_database_url()

# Use QueuePool for direct connections (more reliable than NullPool for production)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,               # Small pool size for Render's resource limits
    max_overflow=3,            # Limited overflow
    pool_pre_ping=True,        # Test connections before use
    pool_recycle=1800,         # Recycle connections every 30 minutes
    pool_timeout=30,           # Wait up to 30 seconds for a connection
    echo=False,                # Disable SQL logging in production
    connect_args={
        "connect_timeout": 30,  # Longer timeout for production
        "application_name": f"winara_app_{os.getenv('RENDER_SERVICE_NAME', 'local')}",
        "options": "-c statement_timeout=30000"  # 30 second query timeout
    }
)

# Add connection event listeners for monitoring
@event.listens_for(engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    logger.info("Database connection established")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug("Connection checked out from pool")

@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    logger.debug("Connection returned to pool")

@event.listens_for(engine, "invalidate")
def receive_invalidate(dbapi_connection, connection_record, exception):
    logger.warning(f"Connection invalidated: {exception}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData()

# Redis connection with error handling
try:
    if settings.REDIS_URL:
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Test Redis connection
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    else:
        redis_client = None
        logger.info("No Redis URL configured")
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}")
    redis_client = None

async def get_redis():
    try:
        if settings.REDIS_URL:
            redis_conn = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_conn.ping()
            return redis_conn
        return None
    except Exception as e:
        logger.warning(f"⚠️ Async Redis connection failed: {e}")
        return None

# Database dependency with retry logic
def get_db():
    db = None
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            db = SessionLocal()
            # Test the connection
            db.execute("SELECT 1")
            yield db
            break
        except Exception as e:
            retry_count += 1
            logger.error(f"Database session error (attempt {retry_count}/{max_retries}): {e}")
            
            if db:
                try:
                    db.rollback()
                    db.close()
                except:
                    pass
                db = None
            
            if retry_count >= max_retries:
                logger.error("Max database connection retries exceeded")
                raise
            else:
                logger.info(f"Retrying database connection in 1 second...")
                import time
                time.sleep(1)
        finally:
            if db and retry_count < max_retries:
                try:
                    db.close()
                except:
                    pass

# Test database connection function with retry
def test_database_connection(max_retries=3):
    """Test the database connection on startup with retry logic"""
    for attempt in range(max_retries):
        try:
            with engine.connect() as connection:
                result = connection.execute("SELECT NOW() as current_time").fetchone()
                logger.info(f"✅ Database connection test successful: {result[0]}")
                return True
        except Exception as e:
            logger.error(f"❌ Database connection test failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
    
    logger.error("Database connection failed after all retry attempts")
    return False

# Health check function
def get_database_health():
    """Get database health status"""
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
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
