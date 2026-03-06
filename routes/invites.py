import uuid
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.group import Group, GroupMember
from models.invite import Invite
from services.email_service import send_invite_email
from services.reconcile_service import reconcile_pending_member
from utils.dependencies import get_current_user, require_group_member

router = APIRouter()


class InviteEmailBody(BaseModel):
    email: str


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    email: str
    token: str
    status: str


class InviteValidateOut(BaseModel):
    message: str
    group_id: uuid.UUID
    email: str


@router.post("/groups/{group_id}/invite", response_model=InviteOut, status_code=201)
async def send_invite(
    group_id: uuid.UUID,
    body: InviteEmailBody,
    current_user: User = Depends(require_group_member),
    db: AsyncSession = Depends(get_db),
):
    """Send invite { email } — adds pending member, creates invite, stubs email."""
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    email = body.email.strip().lower()

    # Check if already a member (by user_id via email lookup or by email)
    result = await db.execute(
        select(User).where(User.email == email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Check if already an active member
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == existing_user.id,
                GroupMember.status == "active",
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="User is already an active member")

    # Check if already a pending member by email
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.email == email,
        )
    )
    existing_pending = result.scalar_one_or_none()

    if not existing_pending:
        # Add as pending group member
        pending_member = GroupMember(
            group_id=group_id,
            email=email,
            status="pending",
        )
        db.add(pending_member)
        await db.flush()

    # Check for existing pending invite
    result = await db.execute(
        select(Invite).where(
            Invite.group_id == group_id,
            Invite.email == email,
            Invite.status == "pending",
        )
    )
    existing_invite = result.scalar_one_or_none()
    if existing_invite:
        raise HTTPException(status_code=400, detail="Invite already pending for this email")

    # Create invite
    token = secrets.token_urlsafe(32)
    invite = Invite(
        group_id=group_id,
        email=email,
        token=token,
        invited_by=current_user.id,
    )
    db.add(invite)
    await db.flush()
    await db.refresh(invite)

    # Send email (stub)
    await send_invite_email(
        to_email=email,
        invite_token=token,
        group_name=group.name,
        inviter_name=current_user.name,
    )

    return InviteOut(
        id=invite.id,
        group_id=invite.group_id,
        email=invite.email,
        token=invite.token,
        status=invite.status,
    )


@router.get("/invites/{token}", response_model=InviteValidateOut)
async def validate_invite(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate + activate invite (reconcile pending member)."""
    result = await db.execute(
        select(Invite).where(Invite.token == token)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    if invite.status != "pending":
        raise HTTPException(status_code=400, detail=f"Invite is already {invite.status}")

    # Check if expired
    if invite.expires_at < datetime.now(timezone.utc):
        invite.status = "expired"
        await db.flush()
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Verify the current user's email matches the invite email
    if current_user.email.lower() != invite.email.lower():
        raise HTTPException(
            status_code=403,
            detail="This invite was sent to a different email address",
        )

    # Mark invite as accepted
    invite.status = "accepted"

    # Reconcile the pending member
    await reconcile_pending_member(
        email=invite.email,
        user_id=current_user.id,
        group_id=invite.group_id,
        db=db,
    )

    await db.flush()

    return InviteValidateOut(
        message="Invite accepted successfully",
        group_id=invite.group_id,
        email=invite.email,
    )
