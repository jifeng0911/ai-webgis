import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from dotenv import  load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL 未在 .env 文件中设置")

engine = create_async_engine(DATABASE_URL, echo=True)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


print(f"数据库引擎已使用 URL: {DATABASE_URL} 初始化")

# 1. 从 .env 获取非异步的 DATABASE_URL
DATABASE_URL_SYNC = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg", "postgresql+psycopg2")
if DATABASE_URL_SYNC == "":
    print("警告：未找到同步 DATABASE_URL。请检查 .env 文件。")
# 2. 创建同步引擎
engine_sync = create_engine(DATABASE_URL_SYNC, echo=False)

print(f"同步数据库引擎已初始化")
