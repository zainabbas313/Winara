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

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    poolclass=NullPool,  # Required for Supavisor transaction mode
    echo=settings.DEBUG
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
