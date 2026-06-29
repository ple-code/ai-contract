from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from ..deps import DB, CurrentUser
from ..models.changelog import ChangeLog
from ..models.clause import Clause, ClauseReviewState
from ..models.contract import Contract, ContractVersion
from ..schemas.clause import AnnotateUpdate, ClauseReviewStateInfo, DecisionUpdate, VersionReviewState
from ..services.audit_service import log_audit

router = APIRouter(prefix="/api/versions", tags=["clauses"])


async def _get_state(db, version_id: int, clause_code: str) -> ClauseReviewState:
    stmt = select(ClauseReviewState).where(
        ClauseReviewState.version_id == version_id,
        ClauseReviewState.clause_code == clause_code,
    )
    state = (await db.execute(stmt)).scalar_one_or_none()
    if not state:
        state = ClauseReviewState(version_id=version_id, clause_code=clause_code)
        db.add(state)
        await db.flush()
    return state


async def _get_contract_id(db, version_id: int) -> int:
    ver = await db.get(ContractVersion, version_id)
    return ver.contract_id if ver else 0


@router.put("/{vid}/clauses/{code}/decision")
async def set_decision(vid: int, code: str, body: DecisionUpdate, request: Request, db: DB, user: CurrentUser):
    state = await _get_state(db, vid, code)
    state.decision = body.decision
    state.updated_by = user.id

    contract_id = await _get_contract_id(db, vid)
    ver = await db.get(ContractVersion, vid)
    event = "accept" if body.decision == "accept" else ("reject" if body.decision == "reject" else "undo_decision")
    db.add(ChangeLog(
        contract_id=contract_id, version_no=ver.version_no if ver else 1,
        event_type=event, clause_code=code,
        detail=f"{'接受' if body.decision == 'accept' else '拒绝' if body.decision == 'reject' else '撤销表态'}",
        actor_user_id=user.id, actor_post=user.post,
    ))
    await log_audit(db, user_id=user.id, user_post=user.post, action=event,
                    target_type="clause", target_id=f"{vid}/{code}",
                    ip=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


@router.put("/{vid}/clauses/{code}/annotate")
async def annotate(vid: int, code: str, body: AnnotateUpdate, request: Request, db: DB, user: CurrentUser):
    state = await _get_state(db, vid, code)
    state.note = body.note if body.note else None
    state.updated_by = user.id

    contract_id = await _get_contract_id(db, vid)
    ver = await db.get(ContractVersion, vid)
    db.add(ChangeLog(
        contract_id=contract_id, version_no=ver.version_no if ver else 1,
        event_type="annotate", clause_code=code,
        detail=body.note[:100] if body.note else "删除批注",
        actor_user_id=user.id, actor_post=user.post,
    ))
    await log_audit(db, user_id=user.id, user_post=user.post, action="annotate",
                    target_type="clause", target_id=f"{vid}/{code}",
                    ip=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


@router.post("/{vid}/clauses/{code}/apply")
async def apply_suggestion(vid: int, code: str, request: Request, db: DB, user: CurrentUser):
    from ..models.review import Finding, Review
    stmt = (select(Finding).join(Review).where(
        Review.version_id == vid, Finding.clause_code == code
    ).order_by(Finding.id.desc()).limit(1))
    finding = (await db.execute(stmt)).scalar_one_or_none()
    if not finding or not finding.suggestion:
        raise HTTPException(400, "无可应用的建议")

    clause_stmt = select(Clause).where(Clause.version_id == vid, Clause.code == code)
    clause = (await db.execute(clause_stmt)).scalar_one_or_none()
    if not clause:
        raise HTTPException(404)

    state = await _get_state(db, vid, code)
    state.applied = True
    state.applied_text_snapshot = clause.text
    state.updated_by = user.id
    clause.text = finding.suggestion

    contract_id = await _get_contract_id(db, vid)
    ver = await db.get(ContractVersion, vid)
    db.add(ChangeLog(
        contract_id=contract_id, version_no=ver.version_no if ver else 1,
        event_type="apply", clause_code=code, detail="应用AI建议",
        actor_user_id=user.id, actor_post=user.post,
    ))
    await log_audit(db, user_id=user.id, user_post=user.post, action="apply",
                    target_type="clause", target_id=f"{vid}/{code}",
                    ip=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


@router.post("/{vid}/clauses/{code}/revert-apply")
async def revert_apply(vid: int, code: str, request: Request, db: DB, user: CurrentUser):
    state = await _get_state(db, vid, code)
    if not state.applied or not state.applied_text_snapshot:
        raise HTTPException(400, "无可撤销的应用")

    clause_stmt = select(Clause).where(Clause.version_id == vid, Clause.code == code)
    clause = (await db.execute(clause_stmt)).scalar_one_or_none()
    if clause:
        clause.text = state.applied_text_snapshot

    state.applied = False
    state.applied_text_snapshot = None
    state.updated_by = user.id

    contract_id = await _get_contract_id(db, vid)
    ver = await db.get(ContractVersion, vid)
    db.add(ChangeLog(
        contract_id=contract_id, version_no=ver.version_no if ver else 1,
        event_type="revert_apply", clause_code=code, detail="撤销应用",
        actor_user_id=user.id, actor_post=user.post,
    ))
    await db.commit()
    return {"ok": True}


@router.get("/{vid}/review-state", response_model=VersionReviewState)
async def get_review_state(vid: int, db: DB, user: CurrentUser):
    stmt = select(ClauseReviewState).where(ClauseReviewState.version_id == vid)
    states = list((await db.execute(stmt)).scalars().all())
    locked = any(s.decision is not None or s.note or s.applied for s in states)
    return VersionReviewState(
        states=[ClauseReviewStateInfo(
            clause_code=s.clause_code, decision=s.decision,
            note=s.note, applied=s.applied,
        ) for s in states],
        stance_locked=locked,
    )
