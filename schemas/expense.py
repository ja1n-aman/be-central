import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ExpenseSplitIn(BaseModel):
    user_id: Optional[uuid.UUID] = None
    email: Optional[str] = None
    value: Decimal

    @field_validator("value")
    @classmethod
    def value_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Split value cannot be negative")
        return v


class ExpenseCreate(BaseModel):
    group_id: uuid.UUID
    description: str
    amount: Decimal
    paid_by: uuid.UUID
    split_type: str
    splits: list[ExpenseSplitIn]

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @field_validator("split_type")
    @classmethod
    def valid_split_type(cls, v: str) -> str:
        allowed = {"equal", "exact", "percentage", "shares"}
        if v not in allowed:
            raise ValueError(f"split_type must be one of {allowed}")
        return v


class ExpenseUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    paid_by: Optional[uuid.UUID] = None
    split_type: Optional[str] = None
    splits: Optional[list[ExpenseSplitIn]] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @field_validator("split_type")
    @classmethod
    def valid_split_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"equal", "exact", "percentage", "shares"}
            if v not in allowed:
                raise ValueError(f"split_type must be one of {allowed}")
        return v


class ExpenseSplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expense_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    email: Optional[str] = None
    value: Decimal
    actual_amount: Decimal
    status: str


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    description: str
    amount: Decimal
    paid_by: uuid.UUID
    split_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    splits: list[ExpenseSplitOut] = []


class ExpenseListResponse(BaseModel):
    items: list[ExpenseOut]
    total: int
    limit: int
    offset: int
