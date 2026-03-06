import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Numeric,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    paid_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    split_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "split_type IN ('equal', 'exact', 'percentage', 'shares')",
            name="ck_expenses_split_type",
        ),
    )

    group = relationship("Group", back_populates="expenses")
    payer = relationship("User", lazy="selectin")
    splits = relationship(
        "ExpenseSplit",
        back_populates="expense",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'pending')", name="ck_expense_splits_status"
        ),
    )

    expense = relationship("Expense", back_populates="splits")
    user = relationship("User", lazy="selectin")
