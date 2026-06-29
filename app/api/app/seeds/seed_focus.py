import asyncio

from sqlalchemy import select

from ..database import async_session
from ..models.config import AppModelConfig

# 岗位 → 关注的条款类型标签（对齐解析器 type_tags 词汇；进入合同时据此自动定位/高亮）
# 把前端写死的 FOCUS_AI 沉到后端，管理员可在「系统配置」里维护，用户也可在「我的关注点」微调
POST_FOCUS = {
    "销售": ["价格", "付款", "交付"],
    "法务": ["违约金", "合同效力", "解除终止", "保密", "知识产权", "争议解决", "数据安全"],
    "商务": ["交付", "质保", "价格"],
    "财务": ["付款", "违约金", "价格"],
}


async def seed():
    async with async_session() as db:
        cfg = (await db.execute(select(AppModelConfig).where(AppModelConfig.id == 1))).scalar_one_or_none()
        if cfg and cfg.post_focus:
            print("→ 岗位审查关注点已初始化，跳过")
            return
        if cfg is None:
            cfg = AppModelConfig(id=1)
            db.add(cfg)
        cfg.post_focus = POST_FOCUS
        await db.commit()
        print("✓ 初始化岗位审查关注点：销售 / 法务 / 商务 / 财务")


if __name__ == "__main__":
    asyncio.run(seed())
