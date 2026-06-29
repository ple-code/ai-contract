STANCE_LABELS = {
    "buyer": "甲方（采购方/买方）",
    "seller": "乙方（供应方/卖方）",
    "neutral": "中立方（公平视角）",
}

STANCE_SYSTEM = {
    "buyer": "你是一名资深法务审查员，以甲方（采购方/买方）的立场审查合同条款。你的职责是保护甲方利益，关注对甲方不利的条款风险。甲方通常处于强势地位，要求按期交货、逾期违约责任越大越好。",
    "seller": "你是一名资深法务审查员，以乙方（供应方/卖方）的立场审查合同条款。你的职责是保护乙方利益，关注对乙方不利的条款风险。乙方通常处于防守地位，希望违约责任越小越好、付款条件越宽松越好。",
    "neutral": "你是一名资深法务审查员，以中立方（公平视角）审查合同条款。你的职责是确保条款公平合理、不偏向任何一方，识别明显不平等条款。",
}


def build_review_prompt(
    clause_title: str,
    clause_text: str,
    stance: str,
    legal_context: str,
    rules_context: str = "",
) -> list[dict]:
    system = STANCE_SYSTEM.get(stance, STANCE_SYSTEM["buyer"])
    if legal_context:
        system += "\n\n" + legal_context
    if rules_context:
        system += "\n\n" + rules_context
    system += """

你的输出必须是严格的JSON格式，包含以下字段：
{
  "risk_level": "high" 或 "mid" 或 "low",
  "finding": "风险发现说明（中文，1-3句话）",
  "suggestion": "修改建议（中文，具体的条款修改方案）",
  "legal_basis": [{"law": "法律名称", "article": "条号", "point": "要点"}],
  "stance_note": "立场化解读（从当前立场分析该条款利弊，1-2句话）"
}

只输出JSON，不要输出其他内容。如果该条款风险较低，risk_level设为"low"，finding说明为什么低风险。"""

    user = f"请审查以下合同条款：\n\n【{clause_title}】\n{clause_text}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


FIELD_EXTRACT_PROMPT = """你是合同关键字段抽取专家。请从以下合同全文中提取关键商务字段。

输出严格JSON格式：
{
  "total_price": "合同总价（如有）",
  "payment_terms": "付款条件/账期（如有）",
  "penalty_rate": "违约金比例（如有）",
  "delivery_date": "交货期限（如有）",
  "warranty_period": "质保期（如有）"
}

只输出JSON，没有的字段填null。"""
