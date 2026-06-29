import asyncio

from sqlalchemy import select

from ..database import async_session, Base, engine
from ..models.user import AppUser
from ..security import hash_password


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        existing = await db.execute(select(AppUser).where(AppUser.username == "admin"))
        if not existing.scalar_one_or_none():
            admin = AppUser(
                username="admin",
                password_hash=hash_password("Admin@123"),
                display_name="管理员",
                post="法务",
                role="管理员",
            )
            db.add(admin)
            await db.commit()
            print("✓ 创建管理员账号: admin / Admin@123")
        else:
            print("→ 管理员账号已存在")


if __name__ == "__main__":
    asyncio.run(seed())
