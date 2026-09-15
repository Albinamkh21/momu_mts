"""Pydantic schemas for the Contract module (validation for create/update/list)."""
from __future__ import annotations

import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ContractStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    TERMINATED = "TERMINATED"


class ContractDirectionType(str, Enum):
    DIRECT_ARTIST = "DIRECT_ARTIST"
    LABEL_CATALOG = "LABEL_CATALOG"


class ContractBase(BaseModel):
    rights_holder_id: int = Field(..., gt=0)
    contract_number: str = Field(..., min_length=1, max_length=255)
    signed_date: Optional[datetime.date] = None
    valid_from: Optional[datetime.date] = None
    valid_to: Optional[datetime.date] = None
    status: ContractStatus = ContractStatus.DRAFT
    direction_type: Optional[ContractDirectionType] = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "ContractBase":
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from не может быть позже valid_to")
        return self


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    contract_number: Optional[str] = Field(None, min_length=1, max_length=255)
    signed_date: Optional[datetime.date] = None
    valid_from: Optional[datetime.date] = None
    valid_to: Optional[datetime.date] = None
    status: Optional[ContractStatus] = None
    direction_type: Optional[ContractDirectionType] = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "ContractUpdate":
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from не может быть позже valid_to")
        return self


class ContractResponse(BaseModel):
    id: int
    rights_holder_id: int = Field(..., validation_alias="right_holder_id", serialization_alias="rights_holder_id")
    right_holder_name: Optional[str] = None
    contract_number: str
    signed_date: Optional[datetime.date] = None
    valid_from: Optional[datetime.date] = None
    valid_to: Optional[datetime.date] = None
    status: ContractStatus
    direction_type: Optional[ContractDirectionType] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class ContractListResponse(BaseModel):
    items: List[ContractResponse]
    total: int
