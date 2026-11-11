from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ExternalContractCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Поля контракта
    contract_number: str
    direction_type: Optional[str] = None
    signed_date: Optional[date] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    # Правообладатель (поля модели RightHolder)
    name: str
    type: str = "INDIVIDUAL"
    alias: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    
    iin_bin: Optional[str] = None
    full_name: Optional[str] = None
    id_document_type: Optional[str] = None
    id_document_number: Optional[str] = None
    id_document_issued_by: Optional[str] = None
    id_document_issue_date: Optional[date] = None
    
    company_name: Optional[str] = None
    director_name: Optional[str] = None
    acting_basis: Optional[str] = None
    
    iban: Optional[str] = None
    bank_name: Optional[str] = None
    bik: Optional[str] = None
    
    # Поля исключительно для Word-шаблона (в БД не сохраняются)
    cn_title: Optional[str] = None
    bank_kbe: Optional[str] = None
    director_short: Optional[str] = None
    
    label_id: Optional[int] = None