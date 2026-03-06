import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _default_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=7)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_default_expires_at, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired')",
            name="ck_invites_status",
        ),
    )

    group = relationship("Group", back_populates="invites")
    inviter = relationship("User", lazy="selectin")
