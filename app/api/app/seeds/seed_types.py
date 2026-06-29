import asyncio

from sqlalchemy import select

from ..database import async_session, Base, engine
from ..models.contract import ContractType


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        existing = await db.execute(select(ContractType).where(ContractType.code == "purchase"))
        if not existing.scalar_one_or_none():
            ct = ContractType(
                code="purchase",
                name="采购合同",
                detect_keywords={
                    "采购合同": 10, "采购方": 5, "供应方": 5,
                    "货物清单": 8, "交货": 4, "验收": 4,
                },
                field_schema=["total_price", "payment_terms", "penalty_rate", "delivery_date", "warranty_period"],
                legal_tags=["价格", "付款", "违约金", "交付", "质保"],
                supported=True,
            )
            db.add(ct)
            await db.commit()
            print("✓ 创建合同类型: 采购合同")
        else:
            print("→ 采购合同类型已存在")


if __name__ == "__main__":
    asyncio.run(seed())
