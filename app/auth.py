import json
import logging
from typing import Optional
from fastapi import Request, Header, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db_session
from app.cache import get_redis_client
from app.models import APIKey

logger = logging.getLogger(__name__)

async def get_current_client_limits(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias=settings.API_KEY_HEADER_NAME),
    db: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    FastAPI dependency that extracts client limits.
    If X-API-Key is present, it validates the key in Postgres (with Redis caching).
    If absent, it falls back to the client IP.
    """
    if not x_api_key:
        # Extract client IP (default to unknown if None)
        ip_addr = request.client.host if request.client else "unknown"
        return {
            "client_id": f"ip:{ip_addr}",
            "capacity": settings.DEFAULT_RATE_LIMIT_CAPACITY,
            "refill_rate": settings.DEFAULT_RATE_LIMIT_REFILL_RATE,
            "authenticated": False
        }
    
    # Check cache first
    redis_conn = get_redis_client()
    cache_key = f"api_key_meta:{x_api_key}"
    
    try:
        cached_meta = await redis_conn.get(cache_key)
        if cached_meta:
            meta = json.loads(cached_meta)
            if not meta.get("valid"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API Key"
                )
            return {
                "client_id": f"key:{meta['client_name']}",
                "capacity": meta["rate_limit_capacity"],
                "refill_rate": meta["rate_limit_refill_rate"],
                "authenticated": True
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to read API key from Redis: %s", str(e))
        # Proceed to DB query on cache error (fail-open cache)
        
    # Query database
    statement = select(APIKey).where(APIKey.key == x_api_key)
    result = await db.execute(statement)
    api_key_record = result.scalar_one_or_none()
    
    if not api_key_record:
        # Cache negative result for 5 minutes to prevent DB hammering
        try:
            await redis_conn.set(cache_key, json.dumps({"valid": False}), ex=300)
        except Exception as e:
            logger.error("Failed to write negative key cache to Redis: %s", str(e))
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
        
    # Determine limits
    capacity = api_key_record.rate_limit_capacity or settings.DEFAULT_RATE_LIMIT_CAPACITY
    refill_rate = api_key_record.rate_limit_refill_rate or settings.DEFAULT_RATE_LIMIT_REFILL_RATE
    
    # Cache positive result for 10 minutes
    meta_to_cache = {
        "valid": True,
        "client_name": api_key_record.client_name,
        "rate_limit_capacity": capacity,
        "rate_limit_refill_rate": refill_rate
    }
    try:
        await redis_conn.set(cache_key, json.dumps(meta_to_cache), ex=600)
    except Exception as e:
        logger.error("Failed to write positive key cache to Redis: %s", str(e))
        
    return {
        "client_id": f"key:{api_key_record.client_name}",
        "capacity": capacity,
        "refill_rate": refill_rate,
        "authenticated": True
    }


# --- User Authentication Helpers (JWT & Hashing) ---

import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from app.models import User

# Configuration for hashing & JWT
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = "super_secret_shortner_key_987654321"  # Fallback secret
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a password using bcrypt."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a secure JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """Retrieves the currently authenticated user from JWT token, if present."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except Exception:
        return None
        
    statement = select(User).where(User.username == username)
    result = await db.execute(statement)
    user = result.scalar_one_or_none()
    return user

async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """Ensures the request is fully authenticated, throwing 401 if not."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in."
        )
    return user

