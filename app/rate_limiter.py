import time
import math
import logging
from fastapi import Request, Response, HTTPException, Depends, status
from app.cache import get_redis_client
from app.config import settings
from app.auth import get_current_client_limits  # We will define this in auth.py

logger = logging.getLogger(__name__)

# Redis Lua Script for Atomically executing Token Bucket Rate Limiting
# Returns array: {allowed_flag (0 or 1), remaining_tokens (string), retry_after (string)}
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Fetch state from Redis Hash
local state = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(state[1])
local last_updated = tonumber(state[2])

if not tokens or not last_updated then
    -- Initialize bucket to full capacity
    tokens = capacity
    last_updated = now
else
    -- Calculate refilled tokens based on time elapsed
    local elapsed = now - last_updated
    if elapsed > 0 then
        local tokens_to_add = elapsed * refill_rate
        tokens = math.min(capacity, tokens + tokens_to_add)
        last_updated = now
    end
end

local allowed = 0
local retry_after = 0

if tokens >= 1 then
    allowed = 1
    tokens = tokens - 1
    -- Save new state only on successful request to minimize writes under spam
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    -- Keep key alive for at least enough time to fully refill
    local ttl = math.ceil(capacity / refill_rate)
    redis.call('EXPIRE', key, ttl)
else
    -- Compute retry-after time
    local missing = 1.0 - tokens
    retry_after = missing / refill_rate
end

return {allowed, tostring(tokens), tostring(retry_after)}
"""

class RateLimiter:
    def __init__(self):
        self.lua_sha = None

    async def _get_lua_sha(self, redis_conn) -> str:
        """Register the Lua script with Redis and return its SHA."""
        if self.lua_sha is None:
            # Load script
            self.lua_sha = await redis_conn.script_load(TOKEN_BUCKET_LUA)
        return self.lua_sha

    async def check_rate_limit(
        self, 
        request: Request, 
        response: Response,
        client_info: dict = Depends(get_current_client_limits)
    ):
        """
        FastAPI Dependency to check rate limit.
        client_info returns a dict with client identity, capacity, and refill rate.
        """
        client_id = client_info["client_id"]
        capacity = client_info["capacity"]
        refill_rate = client_info["refill_rate"]
        
        # Redis key format
        key = f"rate_limit:{client_id}"
        
        now = time.time()
        redis_conn = get_redis_client()
        
        try:
            sha = await self._get_lua_sha(redis_conn)
            # Run using evalsha
            res = await redis_conn.evalsha(sha, 1, key, capacity, refill_rate, now)
            allowed, tokens_str, retry_after_str = res
            
            remaining_tokens = float(tokens_str)
            retry_after = float(retry_after_str)
            
            # Set rate limit headers
            response.headers["X-RateLimit-Limit"] = str(capacity)
            response.headers["X-RateLimit-Remaining"] = str(max(0, int(math.floor(remaining_tokens))))
            
            if not allowed:
                retry_seconds = str(max(1, int(math.ceil(retry_after))))
                # Add headers directly to HTTPException so FastAPI exception handler preserves them
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too Many Requests. Rate limit exceeded.",
                    headers={"Retry-After": retry_seconds, "X-RateLimit-Remaining": "0"}
                )
                
        except HTTPException:
            raise
        except Exception as e:
            # Fail-open if Redis fails to ensure high availability
            logger.error("Rate limiter Redis failure: %s. Failing open.", str(e))
            return

rate_limiter = RateLimiter()
