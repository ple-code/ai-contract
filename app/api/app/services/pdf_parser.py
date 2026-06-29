import re

import pdfplumber

from .doc_parser import ParsedClause, _detect_tags

_CN_NUM = "一二三四五六七八九十百"

_L1_A = re.compile(r"^第[" + _CN_NUM + r"\d]+条\s*")
_L1_B = re.compile(r"^([" + _CN_NUM + r"]+)[、.．]\s*")
_L2 = re.compile(r"^(\d+)[、.．]\s*")
_L3 = re.compile(r"^[（(](\d+)[)）]\s*")
_L3_CN = re.compile(r"^[（(]([" + _CN_NUM + r"]+)[)）]\s*")


def _parse_lines(lines: list[str]) -> list[ParsedClause]:
    clauses: list[ParsedClause] = []
    l1_idx = 0
    l2_idx = 0
    l3_idx = 0
    current_title = ""
    current_text_parts: list[str] = []
    current_level = 0
    current_code = ""

    def flush():
        nonlocal current_title, current_text_parts, current_code, current_level
        if current_code:
            text = "\n".join(current_text_parts).strip()
            tags = _detect_tags(current_title, text)
            clauses.append(ParsedClause(
                code=current_code, title=current_title, text=text,
                level=current_level, type_tags=tags,
            ))
        current_title = ""
        current_text_parts = []
        current_code = ""
        current_level = 0

    preamble_parts: list[str] = []
    started = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        m1a = _L1_A.match(line)
        m1b = _L1_B.match(line) if not m1a else None

        if m1a:
            flush()
            started = True
            l1_idx += 1
            l2_idx = 0
            l3_idx = 0
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
            l2_idx = 0
            l3_idx = 0
            current_level = 1
            current_code = str(l1_idx)
            rest = line[m1b.end():].strip()
            current_title = m1b.group(0).strip() + (" " + rest if rest else "")
            continue

        if started:
            m2 = _L2.match(line)
            m3 = _L3.match(line) if not m2 else None
            m3c = _L3_CN.match(line) if not m2 and not m3 else None

            if m2:
                flush()
                l2_idx += 1
                l3_idx = 0
                current_level = 2
                current_code = f"{l1_idx}-{l2_idx}"
                rest = line[m2.end():].strip()
                current_title = m2.group(0).strip()
                if rest:
                    current_text_parts.append(rest)
                continue

            if m3:
                flush()
                l3_idx += 1
                current_level = 3
                current_code = f"{l1_idx}-{l2_idx}-{l3_idx}"
                rest = line[m3.end():].strip()
                current_title = m3.group(0).strip()
                if rest:
                    current_text_parts.append(rest)
                continue

            if m3c:
                flush()
                l3_idx += 1
                current_level = 3
                current_code = f"{l1_idx}-{l2_idx}-{l3_idx}"
                rest = line[m3c.end():].strip()
                current_title = m3c.group(0).strip()
                if rest:
                    current_text_parts.append(rest)
                continue

        if current_code:
            current_text_parts.append(line)
        elif not started:
            preamble_parts.append(line)

    flush()

    if preamble_parts and not any(c.code == "0" for c in clauses):
        text = "\n".join(preamble_parts).strip()
        if text:
            clauses.insert(0, ParsedClause(
                code="0", title="合同基本信息", text=text,
                level=0, type_tags=_detect_tags("合同基本信息", text),
            ))

    return clauses


def parse_pdf(file_path: str, *, db=None) -> list[ParsedClause]:
    from .ocr_service import is_scanned_pdf, ocr_parse_pdf

    if is_scanned_pdf(file_path):
        full_text = ocr_parse_pdf(file_path)
        return _parse_lines(full_text.split("\n"))

    all_lines: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            all_lines.extend(text.split("\n"))

    return _parse_lines(all_lines)
