from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.cache import close_redis, get_redis_client
from app.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Postgres Database tables
    await init_db()
    # 2. Ensure Redis is initialized early
    get_redis_client()
    yield
    # 3. Gracefully close connections on shutdown
    await close_redis()

app = FastAPI(
    title="Production URL Shortener & Rate Limiter",
    description=(
        "A highly-performant backend engineering project demonstrating custom "
        "Snowflake ID generation, Token Bucket rate limiting via Redis Lua, "
        "and Redis caching with write invalidation."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# Wire in all endpoints
app.include_router(router)

import os
from fastapi.staticfiles import StaticFiles

# Resolve absolute path to app/static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")

# Mount static folder
app.mount("/static", StaticFiles(directory=static_dir), name="static")

