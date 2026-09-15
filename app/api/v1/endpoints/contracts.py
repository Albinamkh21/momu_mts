"""Controller (routes) for the Contract module.

Endpoint -> Controller (this router) -> ContractService -> ContractRepository -> DB
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from __schemas.contracts import (
    ContractCreate,
    ContractDirectionType,
    ContractListResponse,
    ContractResponse,
    ContractStatus,
    ContractUpdate,
)
from services.contract_service import ContractService

router = APIRouter()


@router.get("", response_model=ContractListResponse)
def list_contracts(
    rights_holder_id: Optional[int] = Query(None, gt=0),
    status: Optional[ContractStatus] = Query(None),
    direction_type: Optional[ContractDirectionType] = Query(None),
    search: Optional[str] = Query(None, max_length=255, description="Поиск по номеру договора"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = ContractService(db)
    items, total = service.list(
        right_holder_id=rights_holder_id,
        status_=status,
        direction_type=direction_type,
        search=search,
        limit=limit,
        offset=offset,
    )
    return ContractListResponse(items=items, total=total)


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractService(db).get(contract_id)


@router.post("", response_model=ContractResponse, status_code=201)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
):
    return ContractService(db).create(payload)


@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    payload: ContractUpdate,
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractService(db).update(contract_id, payload)


@router.delete("/{contract_id}", status_code=204)
def delete_contract(
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    ContractService(db).delete(contract_id)
