from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

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
    """Initializes tables in PostgreSQL using SQLModel metadata."""
    from sqlmodel import SQLModel
    # Ensure models are imported so they register on SQLModel.metadata
    from app.models import URL, APIKey, User
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # Handle schema updates for existing tables
        from sqlalchemy import text
        await conn.execute(text("ALTER TABLE urls ADD COLUMN IF NOT EXISTS user_id INTEGER;"))

async def get_db_session():
    """FastAPI Dependency for database sessions."""
    async with async_session() as session:
        yield session
