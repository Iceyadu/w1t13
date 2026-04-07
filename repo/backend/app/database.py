from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


def init_database() -> None:
    """Initialize DB engine/sessionmaker lazily to avoid import-time failures in tests."""
    global engine, async_session_factory
    if engine is not None and async_session_factory is not None:
        return
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


def get_engine() -> AsyncEngine:
    init_database()
    if engine is None:
        raise RuntimeError("Database engine is not initialized")
    return engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    init_database()
    if async_session_factory is None:
        raise RuntimeError("Async session factory is not initialized")
    return async_session_factory


async def get_db() -> AsyncSession:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
