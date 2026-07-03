import pytest
from httpx import AsyncClient
from app.main import app

from sqlmodel import SQLModel
from app.database import engine

@pytest.fixture(scope="module", autouse=True)
async def setup_database():
    # Recreate the connection pool for the current event loop
    engine.pool = engine.pool.recreate()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

@pytest.mark.anyio
async def test_user_registration_and_login():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Register a new user
        reg_payload = {"username": "testuser", "password": "testpassword123"}
        response = await ac.post("/auth/register", json=reg_payload)
        assert response.status_code == 201
        assert response.json() == {"detail": "User registered successfully."}

        # 2. Prevent duplicate registration
        response = await ac.post("/auth/register", json=reg_payload)
        assert response.status_code == 400
        assert "Username is already taken" in response.json()["detail"]

        # 3. Login with invalid credentials
        login_payload_invalid = {"username": "testuser", "password": "wrongpassword"}
        response = await ac.post("/auth/login", json=login_payload_invalid)
        assert response.status_code == 401

        # 4. Login with valid credentials
        login_payload_valid = {"username": "testuser", "password": "testpassword123"}
        response = await ac.post("/auth/login", json=login_payload_valid)
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 5. Fetch current user info (/auth/me)
        response = await ac.get("/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["username"] == "testuser"

        # 6. Shorten URL under user account
        shorten_payload = {"url": "https://docs.pytest.org"}
        response = await ac.post("/shorten", json=shorten_payload, headers=headers)
        assert response.status_code == 201
        short_code = response.json()["short_code"]

        # 7. Get my-urls and verify the shortened link is present
        response = await ac.get("/my-urls", headers=headers)
        assert response.status_code == 200
        my_urls = response.json()
        assert len(my_urls) == 1
        assert my_urls[0]["short_code"] == short_code
        assert my_urls[0]["long_url"] == "https://docs.pytest.org/"
        assert my_urls[0]["click_count"] == 0
