from typing import Optional
import redis.asyncio as redis
from app.config import settings

# Global async Redis client
redis_client: Optional[redis.Redis] = None

def get_redis_client() -> redis.Redis:
    """Gets or initializes the global async Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50
        )
    return redis_client

async def close_redis():
    """Closes the Redis client connection pool."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None

# --- Cache Operations Helper Functions ---

async def get_cached_url(short_code: str) -> Optional[str]:
    """Retrieves long URL from Redis cache."""
    try:
        client = get_redis_client()
        return await client.get(f"url:{short_code}")
    except Exception:
        # Fail-open/graceful degradation if Redis is down
        return None

async def set_cached_url(short_code: str, long_url: str, ttl: int = settings.CACHE_TTL) -> bool:
    """Saves long URL to Redis cache with TTL."""
    try:
        client = get_redis_client()
        await client.set(f"url:{short_code}", long_url, ex=ttl)
        return True
    except Exception:
        return False

async def invalidate_cached_url(short_code: str) -> bool:
    """Invalidates (deletes) short code from Redis cache."""
    try:
        client = get_redis_client()
        await client.delete(f"url:{short_code}")
        return True
    except Exception:
        return False
