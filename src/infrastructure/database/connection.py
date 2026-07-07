import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# Dependency Rule: Domain models might inherit from this Base, 
# but the infrastructure defines it here.
Base = declarative_base()

# Retrieve database URL from environment or use a default SQLite database for local development.
# For async SQLite, we use aiosqlite.
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite+aiosqlite:///./ai_email_assistant.db"
)

# Create an async SQLAlchemy engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQLALCHEMY_ECHO", "False").lower() == "true",
    future=True
)

# Create a sessionmaker that produces AsyncSession objects
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

@asynccontextmanager
async def get_db_session() -> AsyncSession: # type: ignore
    """
    Provide a transactional scope around a series of operations.
    Usage:
        async with get_db_session() as session:
            await session.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
