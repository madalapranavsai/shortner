import asyncio
import pytest
from httpx import AsyncClient
from sqlmodel import SQLModel

from app.main import app
from app.database import engine
from app.cache import get_redis_client, close_redis
from app.config import settings



@pytest.fixture(scope="module", autouse=True)
async def setup_database_and_cache():
    # Recreate the connection pool for the current event loop
    engine.pool = engine.pool.recreate()
    # 1. Initialize Postgres Tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    
    # 2. Flush Redis
    redis_client = get_redis_client()
    try:
        await redis_client.flushdb()
    except Exception:
        pass
        
    yield
    
    # Clean up connections
    await close_redis()


@pytest.mark.anyio
async def test_full_flow():
    # We will run this test sequentially to verify the full flow
    async with AsyncClient(app=app, base_url="http://test") as ac:
        
        # 1. Generate an API Key
        key_res = await ac.post("/keys", json={
            "client_name": "test_client_integration",
            "rate_limit_capacity": 5,
            "rate_limit_refill_rate": 1.0
        })
        assert key_res.status_code == 201
        key_data = key_res.json()
        api_key = key_data["key"]
        assert key_data["client_name"] == "test_client_integration"
        assert api_key is not None
        
        # 2. Test Shortening without API key (anonymous rate limits apply)
        shorten_res = await ac.post("/shorten", json={"url": "https://www.google.com"})
        assert shorten_res.status_code == 201
        url_data = shorten_res.json()
        short_code = url_data["short_code"]
        assert short_code is not None
        assert url_data["long_url"] == "https://www.google.com/"
        
        # 3. Test Redirect (Cache Miss first, then Hit)
        # First redirect (triggers DB query + writes cache)
        redir_res = await ac.get(f"/{short_code}", follow_redirects=False)
        assert redir_res.status_code == 302
        assert redir_res.headers["location"] == "https://www.google.com/"
        
        # Wait a brief moment for the async background task to update DB clicks
        await asyncio.sleep(0.1)
        
        # Check Stats
        stats_res = await ac.get(f"/stats/{short_code}")
        assert stats_res.status_code == 200
        stats_data = stats_res.json()
        assert stats_data["click_count"] == 1
        
        # Second redirect (hits Redis cache directly)
        redir_res2 = await ac.get(f"/{short_code}", follow_redirects=False)
        assert redir_res2.status_code == 302
        assert redir_res2.headers["location"] == "https://www.google.com/"
        
        # Wait for background task
        await asyncio.sleep(0.1)
        
        # Check Stats (should be 2 clicks)
        stats_res2 = await ac.get(f"/stats/{short_code}")
        assert stats_res2.json()["click_count"] == 2
        
        # 4. Test API Key Authentication
        # With valid key
        auth_shorten = await ac.post(
            "/shorten", 
            json={"url": "https://github.com"},
            headers={"X-API-Key": api_key}
        )
        assert auth_shorten.status_code == 201
        auth_url_data = auth_shorten.json()
        auth_short_code = auth_url_data["short_code"]
        
        # With invalid key
        bad_shorten = await ac.post(
            "/shorten", 
            json={"url": "https://github.com"},
            headers={"X-API-Key": "invalid_api_key_123"}
        )
        assert bad_shorten.status_code == 401
        
        # 5. Cache Invalidation & Delete
        # Cache it first by performing a redirect
        redir_auth = await ac.get(f"/{auth_short_code}", follow_redirects=False)
        assert redir_auth.status_code == 302
        
        # Verify it is in cache by getting cached value directly from redis
        redis_client = get_redis_client()
        cached_url = await redis_client.get(f"url:{auth_short_code}")
        assert cached_url == "https://github.com/"
        
        # Delete the URL
        del_res = await ac.delete(f"/{auth_short_code}")
        assert del_res.status_code == 204
        
        # Verify it has been invalidated from Redis cache
        cached_url_after = await redis_client.get(f"url:{auth_short_code}")
        assert cached_url_after is None
        
        # Hitting GET again should return 404
        get_res_deleted = await ac.get(f"/{auth_short_code}", follow_redirects=False)
        assert get_res_deleted.status_code == 404
