from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ReviewRule(Base):
    """确定性审查规则。AI 初审时按条款命中关键词注入 prompt，与模型互补防遗漏。"""
    __tablename__ = "review_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    rule_type: Mapped[str] = mapped_column(String(32))      # 适用类型：采购/通用/销售/...
    match_keywords: Mapped[str] = mapped_column(Text, default="")   # 逗号分隔，命中任一即注入该规则
    condition_desc: Mapped[str] = mapped_column(Text)       # 触发条件描述（展示 + 注入 prompt）
    risk_level: Mapped[str] = mapped_column(String(16))     # high/medium/low
    suggestion: Mapped[str] = mapped_column(Text)           # 处理建议（注入 prompt 指导 AI）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
