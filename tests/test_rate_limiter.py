import asyncio
import time
import pytest
from fastapi import FastAPI, Depends, Response
from fastapi.testclient import TestClient
from httpx import AsyncClient
import redis.asyncio as redis

from app.config import settings
from app.cache import get_redis_client, close_redis
from app.rate_limiter import rate_limiter
from app.auth import get_current_client_limits

# Define a mock/test FastAPI app to isolate rate limiting tests
app = FastAPI()

@app.get("/test-limit", dependencies=[Depends(rate_limiter.check_rate_limit)])
async def mock_endpoint():
    return {"status": "ok"}

# Override dependency to provide predictable limits for testing
async def override_client_limits():
    return {
        "client_id": "test_client",
        "capacity": 3,
        "refill_rate": 2.0,  # 2 tokens per second (0.5s per token)
        "authenticated": False
    }

app.dependency_overrides[get_current_client_limits] = override_client_limits


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def clear_redis():
    # Setup test Redis client
    client = get_redis_client()
    try:
        await client.delete("rate_limit:test_client")
    except Exception:
        pass
    yield
    try:
        await client.delete("rate_limit:test_client")
    except Exception:
        pass
    # Clean up connections
    await close_redis()


@pytest.mark.anyio
async def test_rate_limiter_allow_under_limit():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Capacity is 3, so first 3 requests must pass
        for i in range(3):
            response = await ac.get("/test-limit")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert int(response.headers["X-RateLimit-Remaining"]) == 3 - (i + 1)


@pytest.mark.anyio
async def test_rate_limiter_block_over_limit():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # First 3 consume tokens
        for _ in range(3):
            await ac.get("/test-limit")
            
        # 4th request must be rate limited (429)
        response = await ac.get("/test-limit")
        assert response.status_code == 429
        assert response.json() == {"detail": "Too Many Requests. Rate limit exceeded."}
        assert "Retry-After" in response.headers
        assert int(response.headers["Retry-After"]) >= 1


@pytest.mark.anyio
async def test_rate_limiter_refill():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Consume all tokens
        for _ in range(3):
            await ac.get("/test-limit")
            
        # 4th should fail
        res_fail = await ac.get("/test-limit")
        assert res_fail.status_code == 429
        
        # Wait 0.6 seconds (since refill_rate = 2.0/sec, this refills 1.2 tokens, giving 1 full token)
        await asyncio.sleep(0.6)
        
        # Should now be allowed
        res_success = await ac.get("/test-limit")
        assert res_success.status_code == 200
        assert res_success.json() == {"status": "ok"}
        
        # Immediately after, should fail again
        res_fail_again = await ac.get("/test-limit")
        assert res_fail_again.status_code == 429
