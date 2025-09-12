# database.py
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from redis import Redis
import redis.asyncio as aioredis
from core.config.config import settings
import ssl
import time
from sqlalchemy.exc import OperationalError
import logging

logger = logging.getLogger(__name__)

# Configure SSL for Supabase
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# PostgreSQL Database with retry mechanism
def create_engine_with_retry():
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            engine = create_engine(
                settings.DATABASE_URL,
                connect_args={
                    "sslmode": "require",
                    "sslrootcert": "/etc/ssl/certs/ca-certificates.crt",  # Render's CA path
                    "ssl": ssl_context
                },
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10,
                echo=settings.DEBUG,
                pool_timeout=30  # Increased timeout for Render
            )
            
            # Test connection
            with engine.connect() as test_conn:
                test_conn.execute("SELECT 1")
                
            logger.info("Database connection established successfully")
            return engine
            
        except OperationalError as e:
            retry_count += 1
            logger.warning(f"Database connection failed (attempt {retry_count}/{max_retries}): {e}")
            if retry_count >= max_retries:
                logger.error("Max connection retries exceeded")
                raise
            time.sleep(2 ** retry_count)  # Exponential backoff

engine = create_engine_with_retry()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

# Redis connection with improved configuration
try:
    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True
    )
    # Test Redis connection
    redis_client.ping()
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

async def get_redis():
    try:
        return await aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            retry_on_timeout=True
        )
    except Exception as e:
        logger.error(f"Async Redis connection failed: {e}")
        raise

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    except OperationalError as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# Cache utilities
class CacheKeys:
    USER_SESSION = "user_session:{}"
    ANALYTICS_DASHBOARD = "analytics:dashboard:{}:{}"
    VERTICALS_LIST = "verticals:list"
    TEAM_MEMBERS = "team:members:{}"
    
def get_cache_key(template: str, *args) -> str:
    return template.format(*args)