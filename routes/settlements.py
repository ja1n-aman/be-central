import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.group import GroupMember
from models.settlement import Settlement
from schemas.settlement import SettlementCreate, SettlementOut, SettlementListResponse
from services.balance_service import recompute_balances
from utils.dependencies import get_current_user, require_group_member

router = APIRouter()


@router.post("/settle", response_model=SettlementOut, status_code=201)
async def record_settlement(
    body: SettlementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record settlement { group_id, to_user, amount }."""
    # Verify current user is active member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == body.group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a group member")

    # Verify to_user is active member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == body.group_id,
            GroupMember.user_id == body.to_user,
            GroupMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Recipient is not an active group member")

    if current_user.id == body.to_user:
        raise HTTPException(status_code=400, detail="Cannot settle with yourself")

    settlement = Settlement(
        group_id=body.group_id,
        from_user=current_user.id,
        to_user=body.to_user,
        amount=body.amount,
    )
    db.add(settlement)
    await db.flush()

    # Recompute balances
    await recompute_balances(body.group_id, db)

    await db.refresh(settlement)

    return SettlementOut.model_validate(settlement)


@router.get("/groups/{group_id}/settlements", response_model=SettlementListResponse)
async def list_settlements(
    group_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """Settlement history (with pagination)."""
    base_query = select(Settlement).where(Settlement.group_id == group_id)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(Settlement.settled_at.desc()).limit(limit).offset(offset)
    )
    settlements = result.scalars().all()

    return SettlementListResponse(
        items=[SettlementOut.model_validate(s) for s in settlements],
        total=total,
        limit=limit,
        offset=offset,
    )
