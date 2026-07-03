from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from pydantic import BaseModel, HttpUrl

# --- Database Models ---

from sqlalchemy import BigInteger

class URL(SQLModel, table=True):
    __tablename__ = "urls"
    
    id: int = Field(primary_key=True, sa_type=BigInteger)  # Store custom Snowflake ID (64-bit bigint)
    short_code: str = Field(index=True, unique=True, max_length=20, nullable=False)
    long_url: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    click_count: int = Field(default=0, nullable=False)
    
    # Nullable foreign key linking URL to User
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")


class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False, max_length=50)
    hashed_password: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True, max_length=128, nullable=False)
    client_name: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Custom rate limiting per client; if None, default limits apply
    rate_limit_capacity: Optional[int] = Field(default=None)
    rate_limit_refill_rate: Optional[float] = Field(default=None)


# --- Pydantic Schemas for API Requests & Responses ---

class URLShortenRequest(BaseModel):
    url: HttpUrl


class URLResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    click_count: int


class StatsResponse(BaseModel):
    short_code: str
    long_url: str
    created_at: datetime
    click_count: int


class APIKeyCreateRequest(BaseModel):
    client_name: str
    rate_limit_capacity: Optional[int] = None
    rate_limit_refill_rate: Optional[float] = None


class APIKeyResponse(BaseModel):
    key: str
    client_name: str
    rate_limit_capacity: int
    rate_limit_refill_rate: float


# --- User Auth Pydantic Schemas ---

class UserRegisterRequest(BaseModel):
    username: str
    password: str


class UserLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str

