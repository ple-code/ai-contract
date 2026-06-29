from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# 云端 DB 公网延迟 ~40ms，连接池必须开 pre_ping + recycle：
# 否则云端 PG 空闲断连后，首次 query 会因连接失效触发重试，叠加延迟更慢。
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 借连接前 ping，断连立即重建（避免一次失败 + 重试的 ~80ms）
    pool_recycle=1800,   # 30 分钟回收，小于云端 DB 空闲超时
    pool_timeout=10,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
