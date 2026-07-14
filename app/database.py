import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine for Postgres (uses asyncpg driver)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0
    }
)

# Async session factory
async_session = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def init_db():
    """Initializes tables in PostgreSQL using SQLModel metadata with retries."""
    from sqlmodel import SQLModel
    # Ensure models are imported so they register on SQLModel.metadata
    from app.models import URL, APIKey, User
    
    max_retries = 5
    retry_delay = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
                # Handle schema updates for existing tables
                from sqlalchemy import text
                await conn.execute(text("ALTER TABLE urls ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            logger.info("Database initialized successfully.")
            return
        except Exception as e:
            db_host = "unknown"
            try:
                from urllib.parse import urlparse
                parsed = urlparse(settings.DATABASE_URL)
                db_host = parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc
            except Exception:
                pass
                
            if attempt == max_retries:
                logger.error(f"Failed to initialize database at host '{db_host}' after {max_retries} attempts.")
                raise e
            logger.warning(
                f"Database connection failed to host '{db_host}' (attempt {attempt}/{max_retries}): {e}. "
                f"Retrying in {retry_delay} seconds..."
            )
            await asyncio.sleep(retry_delay)

async def get_db_session():
    """FastAPI Dependency for database sessions."""
    async with async_session() as session:
        yield session
