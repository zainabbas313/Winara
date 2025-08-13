from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from redis import Redis
import redis.asyncio as aioredis
from core.config.config import settings

# Redis connection
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_redis():
    return await aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# Cache utilities
class CacheKeys:
    USER_SESSION = "user_session:{}"
    ANALYTICS_DASHBOARD = "analytics:dashboard:{}:{}"
    VERTICALS_LIST = "verticals:list"
    TEAM_MEMBERS = "team:members:{}"
    
def get_cache_key(template: str, *args) -> str:
    return template.format(*args)