"""Pydantic schemas for the RightHolder module (validation for create/update/list)."""
from __future__ import annotations

import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class RightsHolderType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    COMPANY = "COMPANY"
    IP = "IP"


class RightsHolderBase(BaseModel):
    type: RightsHolderType
    name: str = Field(..., min_length=1, max_length=255, description="ФИО физлица либо название юрлица")
    alias: Optional[str] = Field(None, max_length=255)
    label_id: Optional[int] = None

    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None

    full_name: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    iin_bin: Optional[str] = Field(None, max_length=20)

    id_document_type: Optional[str] = Field(None, max_length=50)
    id_document_number: Optional[str] = Field(None, max_length=50)
    id_document_issued_by: Optional[str] = Field(None, max_length=255)
    id_document_issue_date: Optional[datetime.date] = None

    director_name: Optional[str] = Field(None, max_length=255)
    acting_basis: Optional[str] = Field(None, max_length=255)

    iban: Optional[str] = Field(None, max_length=34)
    bank_name: Optional[str] = Field(None, max_length=255)
    bik: Optional[str] = Field(None, max_length=20)

    @model_validator(mode="after")
    def _validate_type_specific_fields(self) -> "RightsHolderBase":
        if self.type in (RightsHolderType.INDIVIDUAL, RightsHolderType.IP) and not self.full_name:
            raise ValueError("full_name обязателен для физического лица/ИП")
        if self.type == RightsHolderType.COMPANY and not self.company_name:
            raise ValueError("company_name обязателен для юридического лица")
        if self.type in (RightsHolderType.COMPANY, RightsHolderType.IP) and not self.iin_bin:
            raise ValueError("iin_bin обязателен для юридического лица/ИП")
        return self


class RightsHolderCreate(RightsHolderBase):
    pass


class RightsHolderUpdate(BaseModel):
    type: Optional[RightsHolderType] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    alias: Optional[str] = Field(None, max_length=255)
    label_id: Optional[int] = None

    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None

    full_name: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    iin_bin: Optional[str] = Field(None, max_length=20)

    id_document_type: Optional[str] = Field(None, max_length=50)
    id_document_number: Optional[str] = Field(None, max_length=50)
    id_document_issued_by: Optional[str] = Field(None, max_length=255)
    id_document_issue_date: Optional[datetime.date] = None

    director_name: Optional[str] = Field(None, max_length=255)
    acting_basis: Optional[str] = Field(None, max_length=255)

    iban: Optional[str] = Field(None, max_length=34)
    bank_name: Optional[str] = Field(None, max_length=255)
    bik: Optional[str] = Field(None, max_length=20)


class RightsHolderResponse(RightsHolderBase):
    id: int

    model_config = {"from_attributes": True}


class RightsHolderListResponse(BaseModel):
    items: List[RightsHolderResponse]
    total: int
