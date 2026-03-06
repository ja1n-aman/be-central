import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator = relationship("User", back_populates="created_groups", lazy="selectin")
    members = relationship(
        "GroupMember", back_populates="group", lazy="selectin", cascade="all, delete-orphan"
    )
    expenses = relationship(
        "Expense", back_populates="group", lazy="selectin", cascade="all, delete-orphan"
    )
    balances = relationship(
        "Balance", back_populates="group", lazy="selectin", cascade="all, delete-orphan"
    )
    settlements = relationship(
        "Settlement", back_populates="group", lazy="selectin", cascade="all, delete-orphan"
    )
    invites = relationship(
        "Invite", back_populates="group", lazy="selectin", cascade="all, delete-orphan"
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("status IN ('active', 'pending')", name="ck_group_members_status"),
        UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
        UniqueConstraint("group_id", "email", name="uq_group_members_group_email"),
    )

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships", lazy="selectin")
