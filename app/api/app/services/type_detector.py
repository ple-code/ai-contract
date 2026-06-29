PURCHASE_KEYWORDS: dict[str, int] = {
    "采购合同": 10, "采购方": 5, "供应方": 5, "供方": 5,
    "货物清单": 8, "交货": 4, "验收": 4, "乙方交付": 5,
    "甲方支付": 4, "买方": 5, "卖方": 5, "采购": 3,
    "供应商": 4, "需方": 4, "中标": 3, "招标": 3,
}


def detect_contract_type(full_text: str) -> tuple[str, float]:
    score = 0
    for keyword, weight in PURCHASE_KEYWORDS.items():
        count = full_text.count(keyword)
        score += weight * min(count, 3)
    confidence = min(score / 30.0, 1.0)
    if score >= 12:
        return "purchase", confidence
    return "unknown", confidence
