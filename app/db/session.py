from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
    AsyncSession,
)

from app.core.config import settings

# ВАЖНО: одна строка, без переносов! Иначе в URL попадут \n и Postgres не подключится.
DATABASE_URL = (
    f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
    f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
)

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI-зависимость: выдаёт сессию БД и закрывает её после запроса."""
    async with AsyncSessionLocal() as session:
        yield session
