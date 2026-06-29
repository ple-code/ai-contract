"""AI 相似度判断：上传「新合同」时，用 LLM 判断是否与库内已有合同实质相同。

合同编号撞号是确定性匹配（编号字符串相等）；本模块处理的是编号为空 / 编号不一致、
但合同内容（当事人、标的、条款结构）高度雷同的情形——同一笔交易的不同草案/版本，
或同一模板的不同实例。

性能要点：比对只读 ContractVersion.summary（上传时已预生成的合同摘要），
不再重新解析库内合同的条款文本——存量数据再多也只多一次 SELECT。
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.contract import Contract, ContractVersion
from ..services.doc_parser import format_summary_for_cmp
from ..services.model_gateway import chat_completion

logger = logging.getLogger(__name__)

# 相似度阈值：分数 >= 此值才认为是同一合同的不同版本
SIMILARITY_THRESHOLD = 70
# 单次比对的最大候选数（避免提示过长 / 过贵）
MAX_CANDIDATES = 20


async def _gather_candidates(db: AsyncSession, type_code: str) -> list[dict]:
    """取同类型已有合同的摘要。只读 contract + version.summary，不碰条款表。"""
    stmt = (
        select(Contract, ContractVersion.version_no, ContractVersion.summary)
        .join(ContractVersion, ContractVersion.id == Contract.current_version_id, isouter=True)
        .where(Contract.type_code == type_code)
        .order_by(Contract.updated_at.desc())
        .limit(MAX_CANDIDATES)
    )
    rows = (await db.execute(stmt)).all()
    candidates: list[dict] = []
    for row in rows:
        c, ver_no, summary = row[0], row[1], row[2]
        candidates.append({
            "id": c.id,
            "name": c.name,
            "no": c.no,
            "current_version_no": ver_no,
            "summary": summary if isinstance(summary, dict) else {},
        })
    return candidates


def _build_prompt(new_text: str, candidates: list[dict]) -> tuple[str, str]:
    """构造 system / user 提示。"""
    cand_lines = "\n".join(
        f"{i + 1}. id={c['id']}，文件名={c['name'][:40]}，编号={c['no'] or '（无）'}\n"
        f"{format_summary_for_cmp(c['summary'], name=c['name'])}"
        for i, c in enumerate(candidates)
        if c["summary"]  # 跳过无摘要的（旧数据未回填）
    )
    system = (
        "你是合同比对助手，负责判断「新上传的合同」是否与库内已有合同中的某一份实质相同"
        "（同一合同的不同版本/草案，或同一模板的不同实例）。"
        "判断依据（按重要性）：①甲方/当事人是否一致；②整体条款结构（条款标题序列）是否高度雷同；"
        "③合同性质（采购/租赁等）与标的物是否相同；④基本信息措辞是否一致。"
        "关键规则——甲方的处理：\n"
        "  · 若新合同与库内合同的甲方都填写了具体公司名且【一致】→ 强烈支持同一合同（score≥85）。\n"
        "  · 若新合同甲方为空（空白模板，{{ }}占位或未填）而库内合同甲方已填写具体公司名 →"
        "【不是】同一合同（一个是未填模板，一个是已签署的真实合同），match_id 必须为 null、score≤30。\n"
        "  · 若两者甲方都为空且其它信息高度一致 → 可能是同一空白模板，score 可给 70 左右。\n"
        "乙方/金额等字段未填不影响判断（只要甲方判断通过）。措辞/格式/顺序差异不算不同合同。"
        "只返回 JSON。"
    )
    user = (
        f"【新上传合同】\n{new_text}\n\n"
        f"【库内已有合同（同类型，取最近 {len(candidates)} 份）】\n{cand_lines}\n\n"
        "请判断新合同与库内哪一份最可能是同一合同的不同版本/实例。\n"
        '返回 JSON，格式严格为：{"match_id": <合同id整数或null>, '
        '"score": <0到100的整数相似度>, "reason": "<不超过30字的简短理由>"}。\n'
        "务必先比对甲方：甲方一致才可能相似；新合同甲方空而库内已填则一定不相似。\n"
        "若确实没有相似的，match_id 填 null、score 填 0。\n"
        "只返回这一段 JSON。"
    )
    return system, user


def _parse_response(content: str) -> dict | None:
    """从模型回复里抠出 JSON。容错：去 markdown 围栏、取首个 {...} 段。"""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None


async def find_similar_contract(
    db: AsyncSession,
    *,
    new_summary: dict,
    new_name: str,
    type_code: str,
    user_id: int | None = None,
) -> dict | None:
    """用 LLM 判断新合同是否与库内已有合同实质相同。

    只比 new_summary 与库内已存储的 version.summary，不重新解析任何条款。
    Returns: 命中时返回 {id, name, no, current_version_no, score, reason}；否则 None。
    """
    candidates = await _gather_candidates(db, type_code)
    if not candidates:
        return None
    # 全部候选都没摘要（旧数据未回填）→ 无法比对，直接放行
    if not any(c["summary"] for c in candidates):
        return None

    new_text = format_summary_for_cmp(new_summary, name=new_name)
    system, user = _build_prompt(new_text, candidates)

    try:
        resp = await chat_completion(
            db,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            scene="similarity",
            user_id=user_id,
        )
    except Exception as e:
        logger.warning("相似度判断调用模型失败: %s", e)
        return None

    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = _parse_response(content)
    if not parsed:
        logger.info("相似度判断未返回可解析 JSON，原文: %s", content[:200])
        return None

    match_id = parsed.get("match_id")
    score = parsed.get("score", 0)
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0

    if not match_id or score < SIMILARITY_THRESHOLD:
        return None

    for c in candidates:
        if c["id"] == match_id:
            return {
                "id": c["id"],
                "name": c["name"],
                "no": c["no"],
                "current_version_no": c["current_version_no"],
                "score": score,
                "reason": parsed.get("reason", "") or "",
            }
    logger.info("模型返回的 match_id=%s 不在候选中", match_id)
    return None
