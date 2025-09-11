from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from redis import Redis
import redis.asyncio as aioredis
from core.config.config import settings
from sqlalchemy.pool import NullPool
# PostgreSQL Database
# engine = create_engine(
#     settings.DATABASE_URL,
#     poolclass=StaticPool,
#     pool_pre_ping=True,
#     pool_recycle=300,
#     echo=settings.DEBUG
# )

# engine = create_engine(
#     settings.DATABASE_URL,
#     pool_pre_ping=True,
#     poolclass=NullPool,  # Required for Supavisor transaction mode
#     echo=settings.DEBUG
# )


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

# Create database engine
DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=3,
    max_overflow=5,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData()

# Redis connection
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_redis():
    return await aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
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
