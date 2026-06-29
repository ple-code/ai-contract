import re
from dataclasses import dataclass, field

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


@dataclass
class ParsedClause:
    code: str
    title: str
    text: str
    level: int
    type_tags: list[str] = field(default_factory=list)
    # 该条款对应的 body 子元素（w:p / w:tbl）XML 引用，导出修订稿时做原地替换用
    blocks: list = field(default_factory=list)


# 合同编号抽取：匹配「合同编号：XXX」「合同号：XXX」「Contract No.: XXX」
# 值必须以字母/数字开头，避免匹配到"合同编号："后为空的模板占位。
_CONTRACT_NO_PATTERNS = [
    re.compile(r"合\s*同\s*编\s*号\s*[：:]\s*([A-Za-z0-9][A-Za-z0-9\-/_\.]{1,39})"),
    re.compile(r"合\s*同\s*号\s*[：:]\s*([A-Za-z0-9][A-Za-z0-9\-/_\.]{1,39})"),
    re.compile(r"Contract\s*(?:No\.?|Number|#)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9\-/_\.]{1,39})", re.IGNORECASE),
]


def extract_contract_no(text: str) -> str | None:
    """从合同全文中抽取合同编号。模板占位（编号后为空）返回 None。"""
    if not text:
        return None
    for pat in _CONTRACT_NO_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip().rstrip("。.，,")
    return None


# ── 合同摘要提取 ──────────────────────────────────────────────
# 上传时一次性从「合同基本信息」条款里抽出甲方/乙方/时间/地点等结构化字段，
# 存到 ContractVersion.summary，供后续重复合同识别时做快速比对（避免每次重新解析）。
_PARTY_A = re.compile(r"甲\s*方(?:[（(][^）)]*[）)])?\s*[：:]\s*(.+)")
_PARTY_B = re.compile(r"乙\s*方(?:[（(][^）)]*[）)])?\s*[：:]\s*(.+)")
_SIGN_DATE = re.compile(r"(?:签订|签署|签约)\s*(?:日\s*期|时\s*间)\s*[：:]\s*(.+)")
_SIGN_PLACE = re.compile(r"(?:签订|签署|签约)\s*地\s*点\s*[：:]\s*(.+)")

_SUMMARY_FIELD_LIMIT = 80
_INFO_TEXT_LIMIT = 200


def _clean_field(value: str) -> str:
    """清洗字段值：去尾部括号注释/空白/换行，截断。模板占位（{{ xxx }}）视为未填。"""
    if not value:
        return ""
    v = value.strip().split("\n")[0].strip()
    # 去掉「（以下简称甲方）」之类的括号注释
    for sep in ["（", "("]:
        if sep in v:
            v = v.split(sep)[0].strip()
    # 模板占位符 / 全是下划线 / 空白 → 视为未填
    if re.fullmatch(r"[\s_]*", v) or "{{" in v:
        return ""
    return v[:_SUMMARY_FIELD_LIMIT]


def extract_contract_summary(
    clauses: list[ParsedClause],
    *,
    contract_no: str | None,
) -> dict:
    """从已解析条款里提取合同摘要（甲方/乙方/时间/地点/条款结构等）。

    返回 dict，可直接写入 ContractVersion.summary。所有字段缺值为空串。
    """
    info_text = ""
    for c in clauses:
        if c.code == "0":
            info_text = c.text
            break
    if not info_text and clauses:
        info_text = " ".join(c.text for c in clauses[:3] if c.text)

    def _grab(pattern: re.Pattern) -> str:
        m = pattern.search(info_text)
        return _clean_field(m.group(1)) if m else ""

    titles = [c.title.strip() for c in clauses if c.code != "0" and c.title and c.title.strip()]
    return {
        "party_a": _grab(_PARTY_A),
        "party_b": _grab(_PARTY_B),
        "sign_date": _grab(_SIGN_DATE),
        "sign_place": _grab(_SIGN_PLACE),
        "contract_no": contract_no or "",
        "clause_titles": titles[:16],
        "clause_count": len(clauses),
        "info_text": (info_text or "").strip()[:_INFO_TEXT_LIMIT],
    }


def format_summary_for_cmp(summary: dict, *, name: str) -> str:
    """把摘要 dict 格式化成给 LLM 看的紧凑文本（用于重复合同识别比对）。"""
    def _v(k):
        return summary.get(k) or "（未填）"
    titles = summary.get("clause_titles") or []
    struct = " / ".join(titles[:12]) if titles else "（无）"
    return (
        f"甲方：{_v('party_a')}\n"
        f"乙方：{_v('party_b')}\n"
        f"合同编号：{_v('contract_no')}\n"
        f"签订时间：{_v('sign_date')}　签订地点：{_v('sign_place')}\n"
        f"条款结构（{len(titles)}条）：{struct}\n"
        f"基本信息片段：{summary.get('info_text') or '（无）'}"
    )


_CN_NUM = "一二三四五六七八九十百"

_L1_A = re.compile(r"^第[" + _CN_NUM + r"\d]+条\s*")
_L1_B = re.compile(r"^([" + _CN_NUM + r"]+)[、.．]\s*")
_L2 = re.compile(r"^(\d+)[、.．]\s*")
_L3 = re.compile(r"^[（(](\d+)[)）]\s*")
_L3_CN = re.compile(r"^[（(]([" + _CN_NUM + r"]+)[)）]\s*")

TAG_KEYWORDS: dict[str, list[str]] = {
    "价格": ["价格", "金额", "总价", "单价", "合同总价", "费用", "报价"],
    "付款": ["付款", "支付", "账期", "结算", "预付", "尾款"],
    "违约金": ["违约", "赔偿", "罚款", "滞纳金", "违约金"],
    "交付": ["交货", "交付", "发货", "到货", "验收"],
    "质保": ["质量", "质保", "保修", "售后", "三包"],
    "保密": ["保密", "机密", "商业秘密"],
    "知识产权": ["知识产权", "专利", "著作权", "商标"],
    "合同效力": ["生效", "效力", "签章", "盖章"],
    "解除终止": ["解除", "终止", "中止", "退出"],
    "争议解决": ["争议", "仲裁", "诉讼", "管辖"],
    "不可抗力": ["不可抗力"],
    "数据安全": ["数据", "个人信息", "隐私"],
}


def _detect_tags(title: str, text: str) -> list[str]:
    combined = title + text
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            tags.append(tag)
    return tags


def _cn_to_int(s: str) -> int:
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
               "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if len(s) == 1:
        return mapping.get(s, 0)
    if s.startswith("十"):
        return 10 + mapping.get(s[1:], 0) if len(s) > 1 else 10
    if s.endswith("十"):
        return mapping.get(s[0], 0) * 10
    return mapping.get(s, 0)


def _table_rows(tbl) -> list[list[str]]:
    """提取 docx 表格文本，正确处理合并单元格。

    python-docx 的 row.cells 会把横向合并（gridSpan）展开成重复引用、把纵向
    合并（vMerge）的延续格当普通格，导致「价格总计」跨 7 列重复 7 次、跨 3 行
    重复 3 行。这里直接遍历 tr 的子 tc：按 gridSpan 展开补空列保持列数对齐，
    按 vMerge 标记延续格置空（仅 restart 取文本）。
    """
    rows: list[list[str]] = []
    for tr in tbl._tbl.findall(qn("w:tr")):
        out: list[str] = []
        for tc in tr.findall(qn("w:tc")):
            tcPr = tc.find(qn("w:tcPr"))
            is_vm_cont = False
            grid_span = 1
            if tcPr is not None:
                vm = tcPr.find(qn("w:vMerge"))
                if vm is not None and vm.get(qn("w:val")) != "restart":
                    is_vm_cont = True
                gs = tcPr.find(qn("w:gridSpan"))
                if gs is not None:
                    try:
                        grid_span = int(gs.get(qn("w:val")) or "1")
                    except ValueError:
                        pass
            if is_vm_cont:
                out.append("")
            else:
                text = "\n".join(t.text or "" for t in tc.iter(qn("w:t"))).strip()
                out.append(text)
            # gridSpan 横向合并：补空列保持列数对齐（首格已取文本）
            out.extend([""] * (grid_span - 1))
        if any(c.strip() for c in out):
            rows.append(out)
    return rows


def _table_to_markdown(rows: list[list[str]]) -> str:
    """把 docx 表格的二维单元格数据转成 markdown 表格文本（保留结构）。

    前端识别连续的 | ... | 行渲染成 <table>；对 AI/diff 仍是可读纯文本。
    """
    if not rows:
        return ""
    ncol = max((len(r) for r in rows), default=0)
    if ncol == 0:
        return ""
    # 单元格内的换行会切断 markdown 表格行（前端按行匹配），替换成空格；| 会破坏列结构，替换成 /
    rows = [[c.replace("\n", " ").replace("|", "/") for c in r] + [""] * (ncol - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |"]
    out.append("| " + " | ".join("---" for _ in range(ncol)) + " |")
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _block_items(doc) -> list[tuple[str, object]]:
    """按文档顺序遍历段落与表格，返回 (文本, body子元素XML引用) 列表。

    段落：一行文本。表格：转成一段 markdown 表格文本（含表头/分隔行/数据行），
    保证原文件里的表格结构不再被拍平丢失。返回的元素引用用于导出修订稿时
    定位原段落做原地替换（B 方案）。
    """
    items: list[tuple[str, object]] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag
        if tag == qn("w:p"):
            txt = Paragraph(child, doc).text.strip()
            if txt:
                items.append((txt, child))
        elif tag == qn("w:tbl"):
            tbl = Table(child, doc)
            rows = _table_rows(tbl)
            if any(any(c for c in r) for r in rows):
                items.append((_table_to_markdown(rows), child))
    return items


def parse_docx(file_path: str, *, _doc=None) -> list[ParsedClause]:
    doc = _doc or Document(file_path)
    clauses: list[ParsedClause] = []
    l1_idx = 0
    l2_idx = 0
    l3_idx = 0
    current_title = ""
    current_text_parts: list[str] = []
    current_blocks: list = []
    current_level = 0
    current_code = ""

    def flush():
        nonlocal current_title, current_text_parts, current_code, current_level, current_blocks
        if current_code:
            text = "\n".join(current_text_parts).strip()
            tags = _detect_tags(current_title, text)
            clauses.append(ParsedClause(
                code=current_code, title=current_title, text=text,
                level=current_level, type_tags=tags, blocks=list(current_blocks),
            ))
        current_title = ""
        current_text_parts = []
        current_blocks = []
        current_code = ""
        current_level = 0

    preamble_parts: list[str] = []
    preamble_blocks: list = []
    started = False

    for line, elem in _block_items(doc):
        if not line:
            continue

        m1a = _L1_A.match(line)
        m1b = _L1_B.match(line) if not m1a else None

        if m1a:
            flush()
            started = True
            l1_idx += 1
            current_level = 1
            current_code = str(l1_idx)
            header_text = m1a.group(0).strip()
            rest = line[m1a.end():].strip()
            current_title = header_text + (" " + rest if rest else "")
            continue

        if m1b:
            flush()
            started = True
            l1_idx += 1
            current_level = 1
            current_code = str(l1_idx)
            rest = line[m1b.end():].strip()
            current_title = m1b.group(0).strip() + (" " + rest if rest else "")
            continue

        # 子项（1、 （1） （一） 等）不再拆分为独立条款，并入上一级条款正文
        if current_code:
            current_text_parts.append(line)
            current_blocks.append(elem)
        elif not started:
            preamble_parts.append(line)
            preamble_blocks.append(elem)

    flush()

    if preamble_parts and not any(c.code == "0" for c in clauses):
        text = "\n".join(preamble_parts).strip()
        if text:
            clauses.insert(0, ParsedClause(
                code="0", title="合同基本信息", text=text,
                level=0, type_tags=_detect_tags("合同基本信息", text),
                blocks=list(preamble_blocks),
            ))

    return clauses
