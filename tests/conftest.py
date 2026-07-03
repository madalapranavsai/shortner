import os
import sys

# Override environment variables for test execution before app settings load
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:54321/shortner"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ENVIRONMENT"] = "testing"
os.environ["WORKER_ID"] = "1"

import pytest
import asyncio

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


