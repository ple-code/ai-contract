import asyncio

from sqlalchemy import select

from ..database import async_session, Base, engine
from ..models.rule import ReviewRule

# 确定性审查规则：命中 match_keywords（逗号分隔，任一命中）即注入 AI 初审 prompt
RULES = [
    {
        "name": "付款账期上限",
        "rule_type": "采购",
        "match_keywords": "付款,账期,支付,结款,结算",
        "condition_desc": "付款账期 > 60 天",
        "risk_level": "high",
        "suggestion": "账期过长占用资金，建议压缩至 30–60 天或增加预付款。",
    },
    {
        "name": "违约金比例过高/过低",
        "rule_type": "采购",
        "match_keywords": "违约金,违约责任,滞纳金,罚款",
        "condition_desc": "违约金比例 > 30% 或 < 0.5%",
        "risk_level": "medium",
        "suggestion": "过高可能被司法酌减、过低难以约束，建议设在合理区间（如日万分之五、上限合同额 30%）。",
    },
    {
        "name": "缺少质保期条款",
        "rule_type": "采购",
        "match_keywords": "质保,质量保证,保修,缺陷责任",
        "condition_desc": "未检测到「质保/质量保证期」",
        "risk_level": "medium",
        "suggestion": "补充质保期与质保金返还条件，明确缺陷责任。",
    },
    {
        "name": "验收标准不明确",
        "rule_type": "采购",
        "match_keywords": "验收,检验,接收,到货",
        "condition_desc": "验收条款缺少标准/期限",
        "risk_level": "medium",
        "suggestion": "明确验收标准、验收期限及逾期未验收视为合格的规则。",
    },
    {
        "name": "单方解除权失衡",
        "rule_type": "通用",
        "match_keywords": "解除,终止,解除权,提前终止",
        "condition_desc": "仅对方享有任意解除权",
        "risk_level": "high",
        "suggestion": "争取对等解除权或限定解除条件，避免己方被动。",
    },
    {
        "name": "知识产权归属缺失",
        "rule_type": "采购",
        "match_keywords": "知识产权,著作权,专利,版权,成果归属",
        "condition_desc": "定制开发未约定知识产权归属",
        "risk_level": "high",
        "suggestion": "明确成果知识产权归属与授权范围。",
    },
    {
        "name": "保密条款缺失",
        "rule_type": "通用",
        "match_keywords": "保密,机密,confidential,泄密",
        "condition_desc": "未检测到保密义务条款",
        "risk_level": "medium",
        "suggestion": "补充保密范围、期限及违约责任（呼应数据安全法）。",
    },
    {
        "name": "争议解决方式缺失",
        "rule_type": "通用",
        "match_keywords": "争议,管辖,仲裁,诉讼,法院",
        "condition_desc": "未约定管辖法院/仲裁",
        "risk_level": "low",
        "suggestion": "明确争议解决方式与管辖地，建议选择对己方便利的管辖。",
    },
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        existing = await db.execute(select(ReviewRule).limit(1))
        if existing.scalar_one_or_none():
            print("→ 审查规则已存在，跳过")
            return

        for r in RULES:
            db.add(ReviewRule(**r))
        await db.commit()
        print(f"✓ 导入 {len(RULES)} 条审查规则")


if __name__ == "__main__":
    asyncio.run(seed())
