import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.group import GroupMember
from models.expense import ExpenseSplit
from services.balance_service import recompute_balances


async def reconcile_pending_member(
    email: str, user_id: uuid.UUID, group_id: uuid.UUID, db: AsyncSession
) -> None:
    """
    When a pending member activates their invite:
    1. Update all expense_splits where email=email in this group -> set user_id, clear email, status='active'
    2. Update group_members where group_id=group_id and email=email -> set user_id, clear email, status='active', joined_at=now
    3. Recompute balances for this group
    """
    # 1. Update expense splits for this group matching the email
    # Need to find expense_splits where email matches and the expense belongs to this group
    from models.expense import Expense

    result = await db.execute(
        select(ExpenseSplit)
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .where(
            Expense.group_id == group_id,
            ExpenseSplit.email == email,
            ExpenseSplit.status == "pending",
        )
    )
    pending_splits = result.scalars().all()
    for split in pending_splits:
        split.user_id = user_id
        split.email = None
        split.status = "active"

    # 2. Update group member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.email == email,
        )
    )
    member = result.scalar_one_or_none()
    if member:
        member.user_id = user_id
        member.email = None
        member.status = "active"
        member.joined_at = datetime.now(timezone.utc)

    # 3. Recompute balances
    await recompute_balances(group_id, db)
