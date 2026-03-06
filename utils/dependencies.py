import uuid

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.group import GroupMember
from utils.jwt import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_group_member(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a group member")
    return current_user
