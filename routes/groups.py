import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.group import Group, GroupMember
from models.expense import Expense
from schemas.group import (
    GroupCreate,
    GroupOut,
    GroupDetailOut,
    GroupMemberOut,
    GroupListResponse,
    MemberListResponse,
)
from schemas.expense import ExpenseOut, ExpenseListResponse
from utils.dependencies import get_current_user, require_group_member

router = APIRouter()


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new group. Auto-adds creator as active member."""
    group = Group(
        name=body.name,
        created_by=current_user.id,
    )
    db.add(group)
    await db.flush()

    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.flush()
    await db.refresh(group)

    return GroupOut.model_validate(group)


@router.get("", response_model=GroupListResponse)
async def list_groups(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List groups for the current user (with pagination)."""
    base_query = (
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    # Paginated items
    result = await db.execute(
        base_query.order_by(Group.created_at.desc()).limit(limit).offset(offset)
    )
    groups = result.scalars().all()

    return GroupListResponse(
        items=[GroupOut.model_validate(g) for g in groups],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{group_id}", response_model=GroupDetailOut)
async def get_group(
    group_id: uuid.UUID,
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """Get group detail + members."""
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    members = result.scalars().all()

    return GroupDetailOut(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        members=[GroupMemberOut.model_validate(m) for m in members],
    )


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """Delete group (creator only)."""
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group creator can delete this group")

    await db.delete(group)
    await db.flush()


@router.get("/{group_id}/members", response_model=MemberListResponse)
async def list_members(
    group_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """List members (active + pending)."""
    base_query = select(GroupMember).where(GroupMember.group_id == group_id)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(GroupMember.joined_at.desc().nullslast()).limit(limit).offset(offset)
    )
    members = result.scalars().all()

    return MemberListResponse(
        items=[GroupMemberOut.model_validate(m) for m in members],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{group_id}/members/{member_id}", status_code=204)
async def remove_member(
    group_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """Remove member (creator only, can't remove self)."""
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group creator can remove members")

    member = await db.get(GroupMember, member_id)
    if not member or member.group_id != group_id:
        raise HTTPException(status_code=404, detail="Member not found in this group")

    if member.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the group")

    await db.delete(member)
    await db.flush()


@router.get("/{group_id}/expenses", response_model=ExpenseListResponse)
async def list_group_expenses(
    group_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """List expenses in group (with pagination)."""
    base_query = select(Expense).where(Expense.group_id == group_id)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(Expense.created_at.desc()).limit(limit).offset(offset)
    )
    expenses = result.scalars().all()

    return ExpenseListResponse(
        items=[ExpenseOut.model_validate(e) for e in expenses],
        total=total,
        limit=limit,
        offset=offset,
    )
