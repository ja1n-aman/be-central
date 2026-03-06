import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class SettlementCreate(BaseModel):
    group_id: uuid.UUID
    to_user: uuid.UUID
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    from_user: uuid.UUID
    to_user: uuid.UUID
    amount: Decimal
    settled_at: datetime


class SettlementListResponse(BaseModel):
    items: list[SettlementOut]
    total: int
    limit: int
    offset: int
