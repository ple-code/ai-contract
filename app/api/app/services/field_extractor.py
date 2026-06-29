"""关键字段抽取器。

从条款文本里抽取合同总价 / 付款账期 / 违约金比例 / 交货期 等关键字段的数值，
用于在工作台顶部呈现「关键字段变更摘要」（基准 → 当前 的字段级 from→to）。

抽取基于正则 + 条款类型标签（type_tags）定位，确定性强、可解释；
与 AI 审查互补，给人工复核一个一眼可见的「核心商业条款变了什么」。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class FieldChange:
    field: str
    from_value: str
    to_value: str
    change_type: str  # mod / add / del


def _fmt_money(raw: str) -> str:
    """金额格式化：去全/半角逗号 → 转 float → 三位分隔（整数不带小数）。"""
    cleaned = raw.replace(",", "").replace("，", "").strip()
    try:
        n = float(cleaned)
    except ValueError:
        return raw
    return f"{int(n):,}" if n == int(n) else f"{n:,.2f}"


# 每个关键字段：(字段名, 关联 type_tag, 正则, 格式化函数)
# 正则只捕获需要展示的核心数值部分（含单位），避免把整句话放进来。
_FIELDS: list[tuple[str, str, str, Callable[[re.Match], str]]] = [
    (
        "合同总价",
        "价格",
        # 「合同总价/总金额/... 人民币：X 元 / X 万元」允许中间的：: 空格 大写
        r"(?:合同总价|总金额|合同金额|总货款|货款总计|总价|价款|合计金额)"
        r"[为是约]?\s*(?:人民币)?\s*[：:]?\s*(?:RMB|￥|¥)?\s*([\d,，.]+)\s*(万元|元)",
        lambda m: _fmt_money(m.group(1))
        + (" 万元" if m.group(2) == "万元" else " 元"),
    ),
    (
        "付款账期",
        "付款",
        # 必须有付款上下文（付款/支付/结算/账款）在 X天/日 附近，避免误抓交货期
        r"(?:付款|支付|结算|账款|货款)[^。；;]{0,20}?(\d+)\s*个?\s*(?:工作)?([天日])"
        r"|(\d+)\s*个?\s*(?:工作)?([天日])[^。；;]{0,12}?(?:内付款|付款|支付)",
        lambda m: (m.group(1) or m.group(3)) + (m.group(2) or m.group(4)),
    ),
    (
        "违约金比例",
        "违约金",
        # 「每日按 … 的 X‰ / X%」
        r"([\d.]+)\s*([‰％%])",
        lambda m: m.group(1) + "‰",
    ),
    (
        "交货期",
        "交付",
        # 必须有交付上下文（交货/交付/发货/到货/送货）在 X天/日 附近，避免误抓付款期
        r"(?:交货|交付|发货|到货|送货)[^。；;]{0,20}?(\d+)\s*个?\s*(?:工作)?([天日])"
        r"|(\d+)\s*个?\s*(?:工作)?([天日])[^。；;]{0,12}?(?:内交货|交货|交付|到货)",
        lambda m: (m.group(1) or m.group(3)) + (m.group(2) or m.group(4)),
    ),
]


def extract_value(field_name: str, tag: str, pattern: str,
                  fmt: Callable[[re.Match], str], text: str) -> str | None:
    if not text:
        return None
    m = re.search(pattern, text)
    if m:
        return fmt(m)
    return None


def summarize_field_changes(
    diff_items: list[dict],
    current_clauses: list[dict],
) -> list[FieldChange]:
    """根据 diff 条目 + 当前版本条款（含 type_tags），产出关键字段变更列表。

    diff_items: [{clause_code, change_type, old_text, new_text}, ...]
    current_clauses: [{code, type_tags: [str]}, ...]
    """
    # 建立 clause_code -> type_tags 映射（以当前版本条款为准）
    tag_by_code: dict[str, list[str]] = {}
    for c in current_clauses:
        tag_by_code[c.get("code", "")] = c.get("type_tags") or []

    changes: list[FieldChange] = []

    for field_name, tag, pattern, fmt in _FIELDS:
        # 找到含该标签、且在本轮 diff 里发生变更的条款
        matched_codes = [
            it["clause_code"]
            for it in diff_items
            if tag in tag_by_code.get(it.get("clause_code", ""), [])
        ]

        old_val: str | None = None
        new_val: str | None = None
        change_type = "mod"

        for code in matched_codes:
            item = next((it for it in diff_items if it["clause_code"] == code), None)
            if not item:
                continue
            ct = item.get("change_type", "mod")
            old_t = item.get("old_text") or ""
            new_t = item.get("new_text") or ""

            o = extract_value(field_name, tag, pattern, fmt, old_t)
            n = extract_value(field_name, tag, pattern, fmt, new_t)

            if ct == "add":
                # 新增条款：只有新值
                if n and not new_val:
                    new_val, change_type = n, "add"
            elif ct == "del":
                # 删除条款：只有旧值
                if o and not old_val:
                    old_val, change_type = o, "del"
            else:
                # 修改：两边都有，取第一个发生变化的
                if o and n and o != n and not old_val:
                    old_val, new_val, change_type = o, n, "mod"

        if old_val or new_val:
            changes.append(FieldChange(
                field=field_name,
                from_value=old_val or "",
                to_value=new_val or "",
                change_type=change_type,
            ))

    return changes
