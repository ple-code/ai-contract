import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..deps import DB, CurrentUser
from ..models.clause import Clause, ClauseReviewState
from ..models.review import Finding, Review
from ..schemas.clause import VersionReviewState, ClauseReviewStateInfo
from ..schemas.review import FindingInfo, ReviewDetail, ReviewRequest
from ..services.review_engine import is_stance_locked, run_review

router = APIRouter(prefix="/api", tags=["reviews"])


def _norm_legal_basis(raw) -> list[dict]:
    """AI 返回的法律依据字段名不统一（article/point vs article_no/snippet），
    统一成前端 FindingInfo 期望的 article_no / snippet。"""
    if not raw:
        return []
    out = []
    for lb in raw:
        if not isinstance(lb, dict):
            continue
        out.append({
            "law": lb.get("law") or "",
            "article_no": lb.get("article_no") or lb.get("article") or lb.get("articles") or "",
            "snippet": lb.get("snippet") or lb.get("point") or lb.get("content") or "",
        })
    return out


@router.post("/reviews")
async def start_review(body: ReviewRequest, db: DB, user: CurrentUser):
    locked = await is_stance_locked(db, body.version_id)
    if locked:
        raise HTTPException(409, "已有复审留痕，立场已锁定，无法重新初审")

    async def event_generator():
        async for event in run_review(db, body.version_id, user.id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/reviews/{review_id}", response_model=ReviewDetail)
async def get_review(review_id: int, db: DB, user: CurrentUser):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(404)
    stmt = select(Finding).where(Finding.review_id == review.id)
    findings = list((await db.execute(stmt)).scalars().all())
    return ReviewDetail(
        id=review.id, version_id=review.version_id, stance=review.stance,
        model_used=review.model_used, status=review.status,
        findings=[FindingInfo(
            id=f.id, clause_code=f.clause_code, risk_level=f.risk_level,
            finding=f.finding, suggestion=f.suggestion,
            legal_basis=_norm_legal_basis(f.legal_basis), stance_note=f.stance_note,
        ) for f in findings],
    )


@router.get("/reviews/by-version/{version_id}", response_model=ReviewDetail | None)
async def get_review_by_version(version_id: int, db: DB, user: CurrentUser, stance: str | None = None):
    stmt = select(Review).where(Review.version_id == version_id)
    if stance:
        stmt = stmt.where(Review.stance == stance)
    stmt = stmt.order_by(Review.id.desc()).limit(1)
    review = (await db.execute(stmt)).scalar_one_or_none()
    if not review:
        return None
    stmt2 = select(Finding).where(Finding.review_id == review.id)
    findings = list((await db.execute(stmt2)).scalars().all())
    return ReviewDetail(
        id=review.id, version_id=review.version_id, stance=review.stance,
        model_used=review.model_used, status=review.status,
        findings=[FindingInfo(
            id=f.id, clause_code=f.clause_code, risk_level=f.risk_level,
            finding=f.finding, suggestion=f.suggestion,
            legal_basis=_norm_legal_basis(f.legal_basis), stance_note=f.stance_note,
        ) for f in findings],
    )


@router.put("/reviews/{review_id}/stance", response_model=ReviewDetail)
async def switch_stance(review_id: int, db: DB, user: CurrentUser, stance: str = "buyer"):
    """三立场初审已全部预生成，切换立场直接返回目标立场结果（不再重新调 AI）。"""
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(404)
    stmt = select(Review).where(Review.version_id == review.version_id, Review.stance == stance).order_by(Review.id.desc()).limit(1)
    target = (await db.execute(stmt)).scalar_one_or_none()
    if not target:
        raise HTTPException(404, f"立场 {stance} 的初审结果不存在，请重新初审")
    findings_stmt = select(Finding).where(Finding.review_id == target.id).order_by(Finding.id)
    findings = list((await db.execute(findings_stmt)).scalars().all())
    return ReviewDetail(
        id=target.id, version_id=target.version_id, stance=target.stance,
        model_used=target.model_used, status=target.status,
        findings=[FindingInfo(
            id=f.id, clause_code=f.clause_code, risk_level=f.risk_level,
            finding=f.finding, suggestion=f.suggestion,
            legal_basis=_norm_legal_basis(f.legal_basis), stance_note=f.stance_note,
        ) for f in findings],
    )
