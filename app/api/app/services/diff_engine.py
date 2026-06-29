import difflib
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .doc_parser import ParsedClause


@dataclass
class DiffChange:
    clause_code: str
    change_type: str  # add / del / mod
    old_title: str | None = None
    new_title: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    inline_diff_html: str | None = None


def _inline_diff_html(old: str, new: str) -> str:
    sm = difflib.SequenceMatcher(None, old, new)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(_escape(old[i1:i2]))
        elif tag == "delete":
            parts.append(f'<del class="d">{_escape(old[i1:i2])}</del>')
        elif tag == "insert":
            parts.append(f'<ins class="i">{_escape(new[j1:j2])}</ins>')
        elif tag == "replace":
            parts.append(f'<del class="d">{_escape(old[i1:i2])}</del>')
            parts.append(f'<ins class="i">{_escape(new[j1:j2])}</ins>')
    return "".join(parts)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def compute_diff(baseline: list[ParsedClause], current: list[ParsedClause]) -> list[DiffChange]:
    baseline_map: dict[str, ParsedClause] = {}
    for c in baseline:
        baseline_map[c.code] = c

    current_map: dict[str, ParsedClause] = {}
    for c in current:
        current_map[c.code] = c

    used_baseline: set[str] = set()
    changes: list[DiffChange] = []

    for cur in current:
        best_match: ParsedClause | None = None
        best_score = 0.0

        if cur.code in baseline_map:
            bc = baseline_map[cur.code]
            score = fuzz.ratio(cur.title + cur.text, bc.title + bc.text)
            if score > 30:
                best_match = bc
                best_score = score

        if not best_match:
            for bc in baseline:
                if bc.code in used_baseline:
                    continue
                title_score = fuzz.ratio(cur.title, bc.title)
                text_score = fuzz.ratio(cur.text[:200], bc.text[:200])
                combined = title_score * 0.4 + text_score * 0.6
                if combined > best_score and combined > 50:
                    best_match = bc
                    best_score = combined

        if best_match:
            used_baseline.add(best_match.code)
            if best_match.text.strip() != cur.text.strip() or best_match.title.strip() != cur.title.strip():
                html = _inline_diff_html(best_match.text, cur.text)
                changes.append(DiffChange(
                    clause_code=cur.code, change_type="mod",
                    old_title=best_match.title, new_title=cur.title,
                    old_text=best_match.text, new_text=cur.text,
                    inline_diff_html=html,
                ))
        else:
            changes.append(DiffChange(
                clause_code=cur.code, change_type="add",
                new_title=cur.title, new_text=cur.text,
            ))

    for bc in baseline:
        if bc.code not in used_baseline:
            changes.append(DiffChange(
                clause_code=bc.code, change_type="del",
                old_title=bc.title, old_text=bc.text,
            ))

    return changes
