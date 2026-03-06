import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_id: uuid.UUID
    from_user: uuid.UUID
    to_user: uuid.UUID
    amount: Decimal
    last_updated: datetime


class BalanceListResponse(BaseModel):
    items: list[BalanceOut]
    total: int
    limit: int
    offset: int
