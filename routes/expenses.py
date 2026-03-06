import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.group import Group, GroupMember
from models.expense import Expense, ExpenseSplit
from schemas.expense import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseOut,
    ExpenseSplitOut,
    ExpenseListResponse,
)
from services.split_engine import compute_splits
from services.balance_service import recompute_balances
from utils.dependencies import get_current_user, require_group_member

router = APIRouter()


async def _validate_expense_members(
    group_id: uuid.UUID,
    paid_by: uuid.UUID,
    splits_in: list,
    db: AsyncSession,
) -> None:
    """Validate that paid_by and all split members are group members."""
    # Fetch all group members
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    group_members = result.scalars().all()

    active_user_ids = {m.user_id for m in group_members if m.user_id and m.status == "active"}
    all_user_ids = {m.user_id for m in group_members if m.user_id}
    all_emails = {m.email for m in group_members if m.email}

    # paid_by must be active group member
    if paid_by not in active_user_ids:
        raise HTTPException(
            status_code=400, detail="paid_by must be an active group member"
        )

    # Validate each split member
    for s in splits_in:
        if s.user_id is not None:
            if s.user_id not in all_user_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Split user {s.user_id} is not a group member",
                )
        elif s.email is not None:
            if s.email not in all_emails:
                raise HTTPException(
                    status_code=400,
                    detail=f"Split email {s.email} is not a group member",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Each split must have either user_id or email",
            )

    # Pending member (email-only) cannot be paid_by — already enforced above since
    # paid_by must be in active_user_ids


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    body: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create expense (with splits, validated)."""
    # Check current user is group member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == body.group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a group member")

    # Validate at least 2 members in split
    if len(body.splits) < 2:
        raise HTTPException(
            status_code=400, detail="At least 2 members required in split"
        )

    # Validate members
    await _validate_expense_members(body.group_id, body.paid_by, body.splits, db)

    # Compute splits
    members_data = [
        {
            "user_id": str(s.user_id) if s.user_id else None,
            "email": s.email,
            "value": s.value,
        }
        for s in body.splits
    ]
    try:
        computed = compute_splits(body.amount, members_data, body.split_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create expense
    expense = Expense(
        group_id=body.group_id,
        description=body.description,
        amount=body.amount,
        paid_by=body.paid_by,
        split_type=body.split_type,
    )
    db.add(expense)
    await db.flush()

    # Create splits
    split_models = []
    for c in computed:
        user_id_val = uuid.UUID(c["user_id"]) if c["user_id"] else None
        status = "active" if user_id_val else "pending"
        split_obj = ExpenseSplit(
            expense_id=expense.id,
            user_id=user_id_val,
            email=c["email"],
            value=c["value"],
            actual_amount=c["actual_amount"],
            status=status,
        )
        db.add(split_obj)
        split_models.append(split_obj)

    await db.flush()

    # Recompute balances
    await recompute_balances(body.group_id, db)

    # Refresh to get all relationships
    await db.refresh(expense)

    return ExpenseOut.model_validate(expense)


@router.put("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: uuid.UUID,
    body: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit expense (delete old splits, create new)."""
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Check current user is group member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == expense.group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a group member")

    # Apply updates
    if body.description is not None:
        expense.description = body.description
    if body.amount is not None:
        expense.amount = body.amount
    if body.paid_by is not None:
        expense.paid_by = body.paid_by
    if body.split_type is not None:
        expense.split_type = body.split_type

    # If splits are provided, replace them
    if body.splits is not None:
        if len(body.splits) < 2:
            raise HTTPException(
                status_code=400, detail="At least 2 members required in split"
            )

        await _validate_expense_members(
            expense.group_id, expense.paid_by, body.splits, db
        )

        # Delete old splits
        result = await db.execute(
            select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id)
        )
        old_splits = result.scalars().all()
        for old in old_splits:
            await db.delete(old)
        await db.flush()

        # Compute new splits
        members_data = [
            {
                "user_id": str(s.user_id) if s.user_id else None,
                "email": s.email,
                "value": s.value,
            }
            for s in body.splits
        ]
        try:
            computed = compute_splits(expense.amount, members_data, expense.split_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        for c in computed:
            user_id_val = uuid.UUID(c["user_id"]) if c["user_id"] else None
            status = "active" if user_id_val else "pending"
            split_obj = ExpenseSplit(
                expense_id=expense.id,
                user_id=user_id_val,
                email=c["email"],
                value=c["value"],
                actual_amount=c["actual_amount"],
                status=status,
            )
            db.add(split_obj)

    await db.flush()

    # Recompute balances
    await recompute_balances(expense.group_id, db)

    await db.refresh(expense)

    return ExpenseOut.model_validate(expense)


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete expense."""
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Check current user is group member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == expense.group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a group member")

    group_id = expense.group_id
    await db.delete(expense)
    await db.flush()

    # Recompute balances
    await recompute_balances(group_id, db)
