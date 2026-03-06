import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.balance import Balance
from schemas.balance import BalanceOut, BalanceListResponse
from utils.dependencies import require_group_member

router = APIRouter()


@router.get("/groups/{group_id}/balances", response_model=BalanceListResponse)
async def get_group_balances(
    group_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """Get current balances for the group."""
    base_query = select(Balance).where(Balance.group_id == group_id)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(Balance.amount.desc()).limit(limit).offset(offset)
    )
    balances = result.scalars().all()

    return BalanceListResponse(
        items=[BalanceOut.model_validate(b) for b in balances],
        total=total,
        limit=limit,
        offset=offset,
    )
