# database.py
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from redis import Redis
import redis.asyncio as aioredis
from core.config.config import settings
import ssl

# PostgreSQL Database with Supabase
def create_engine_with_ssl():
    return create_engine(
        settings.DATABASE_URL,
        connect_args={
            "sslmode": "require",
            "sslrootcert": "/path/to/ssl/cert"  # Only if required by Supabase
        },
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
        echo=settings.DEBUG
    )

engine = create_engine_with_ssl()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

# Redis connection (adjust for production Redis)
redis_client = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None  # Adjust based on your Redis provider
)

async def get_redis():
    return await aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        ssl_cert_reqs=None
    )

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Cache utilities (unchanged)
class CacheKeys:
    USER_SESSION = "user_session:{}"
    ANALYTICS_DASHBOARD = "analytics:dashboard:{}:{}"
    VERTICALS_LIST = "verticals:list"
    TEAM_MEMBERS = "team:members:{}"
    
def get_cache_key(template: str, *args) -> str:
    return template.format(*args)