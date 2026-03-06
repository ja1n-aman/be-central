import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class GroupCreate(BaseModel):
    name: str


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime


class GroupMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    email: Optional[str] = None
    status: str
    joined_at: Optional[datetime] = None


class GroupDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime
    members: list[GroupMemberOut] = []


class GroupListResponse(BaseModel):
    items: list[GroupOut]
    total: int
    limit: int
    offset: int


class MemberListResponse(BaseModel):
    items: list[GroupMemberOut]
    total: int
    limit: int
    offset: int
