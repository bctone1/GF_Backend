# schemas/user/account_delete.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import ConfigDict

from schemas.base import ORMBase
from schemas.enums import AccountDeletionStatus  # expected: 'pending' | 'processing' | 'completed' | 'rejected'


# =========================================
# user.account_deletion_requests
# =========================================
class AccountDeletionRequestCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    notes: Optional[str] = None  # optional reason or context


class AccountDeletionRequestUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    status: Optional[AccountDeletionStatus] = None
    notes: Optional[str] = None  # allow operator to append clarification


class AccountDeletionRequestResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    request_id: int
    user_id: int
    status: AccountDeletionStatus
    requested_at: datetime
    processed_at: Optional[datetime] = None
    notes: Optional[str] = None
