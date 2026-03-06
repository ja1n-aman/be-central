import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.expense import Expense, ExpenseSplit
from models.settlement import Settlement
from models.balance import Balance


async def recompute_balances(group_id: uuid.UUID, db: AsyncSession) -> None:
    """
    Full recompute of net balances for a group.

    1. Fetch all expenses + their active splits for this group.
    2. Build net dict: {(from_user, to_user): Decimal}.
    3. For each expense: each split member (except payer) owes paid_by the actual_amount.
    4. Subtract settlements: each settlement reduces from_user->to_user balance.
    5. Simplify: if A owes B x and B owes A y, net = one direction only.
    6. Delete all old balance rows for group.
    7. Insert new balance rows (only positive amounts).
    """
    # 1. Fetch expenses with active splits
    result = await db.execute(
        select(Expense).where(Expense.group_id == group_id)
    )
    expenses = result.scalars().all()

    net: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = defaultdict(Decimal)

    # 2 & 3. Build net from expense splits
    for expense in expenses:
        paid_by = expense.paid_by
        for split in expense.splits:
            # Only process active splits with a user_id (skip pending email-only)
            if split.user_id is None:
                continue
            if split.status != "active":
                continue
            if split.user_id == paid_by:
                continue
            # split.user_id owes paid_by the actual_amount
            net[(split.user_id, paid_by)] += split.actual_amount

    # 4. Subtract settlements
    result = await db.execute(
        select(Settlement).where(Settlement.group_id == group_id)
    )
    settlements = result.scalars().all()

    for s in settlements:
        net[(s.from_user, s.to_user)] -= s.amount

    # 5. Simplify — collapse bidirectional debts
    simplified: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
    processed: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for (a, b), amount in net.items():
        if (a, b) in processed or (b, a) in processed:
            continue
        reverse = net.get((b, a), Decimal("0"))
        net_amount = amount - reverse
        if net_amount > Decimal("0"):
            simplified[(a, b)] = net_amount
        elif net_amount < Decimal("0"):
            simplified[(b, a)] = abs(net_amount)
        # If exactly 0, omit
        processed.add((a, b))
        processed.add((b, a))

    # 6. Delete old balance rows
    await db.execute(
        delete(Balance).where(Balance.group_id == group_id)
    )

    # 7. Insert new balance rows
    for (from_user, to_user), amount in simplified.items():
        if amount > Decimal("0"):
            balance = Balance(
                group_id=group_id,
                from_user=from_user,
                to_user=to_user,
                amount=amount,
            )
            db.add(balance)

    await db.flush()
