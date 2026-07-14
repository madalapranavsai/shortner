from pydantic_settings import BaseSettings
from pydantic import model_validator

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shortner"
    REDIS_URL: str = "redis://localhost:6379/0"
    ENVIRONMENT: str = "development"
    WORKER_ID: int = 1
    
    # Auth config
    API_KEY_HEADER_NAME: str = "X-API-Key"
    
    # Default rate limits (applied if no custom limits on the API Key)
    DEFAULT_RATE_LIMIT_CAPACITY: int = 10          # Max requests allowed in bucket burst
    DEFAULT_RATE_LIMIT_REFILL_RATE: float = 1.0     # Tokens refilled per second (e.g. 1 req/sec average)
    
    # Cache configuration (in seconds)
    CACHE_TTL: int = 3600

    @model_validator(mode="after")
    def adjust_database_url(self) -> "Settings":
        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
