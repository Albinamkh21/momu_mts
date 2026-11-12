"""Controller (routes) for the Contract module.

Endpoint -> Controller (this router) -> ContractService -> ContractRepository -> DB
"""
from __future__ import annotations

from typing import Optional

from __schemas.external_contract import ExternalContractCreateRequest
from __schemas.contract_annex import (
    AnnexItemCreate,
    AnnexItemResponse,
    AnnexItemUpdate,
    ContractAnnexCreate,
    ContractAnnexListResponse,
    ContractAnnexResponse,
    ContractAnnexUpdate,
    IncomingAnnexPayload,
)
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
from services.contract_annex_service import ContractAnnexService

router = APIRouter()


@router.get("", response_model=ContractListResponse)
def list_contracts(
    rights_holder_id: Optional[int] = Query(None, gt=0),
    status: Optional[ContractStatus] = Query(None),
    direction_type: Optional[ContractDirectionType] = Query(None),
    search: Optional[str] = Query(None, max_length=255, description="Поиск по номеру договора"),
    sort_by: Optional[str] = Query(None, description="Поле сортировки"),
    sort_dir: str = Query("desc", description="Направление сортировки: asc или desc"),
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
        sort_by=sort_by,
        sort_dir=sort_dir if sort_dir == "asc" else "desc",
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


# ── Contract Annexes (nested CRUD, ContractAnnex belongs to a Contract) ─────

@router.get("/{contract_id}/annexes", response_model=ContractAnnexListResponse)
def list_contract_annexes(
    contract_id: int = Path(..., gt=0),
    search: Optional[str] = Query(None, max_length=50, description="Поиск по номеру приложения"),
    sort_by: Optional[str] = Query(None, description="Поле сортировки"),
    sort_dir: str = Query("asc", description="Направление сортировки: asc или desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = ContractAnnexService(db)
    items, total = service.list_by_contract(
        contract_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir if sort_dir == "desc" else "asc",
        limit=limit,
        offset=offset,
    )
    return ContractAnnexListResponse(items=items, total=total)


@router.post("/{contract_id}/annexes", response_model=ContractAnnexResponse, status_code=201)
def create_contract_annex(
    payload: ContractAnnexCreate,
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).create(contract_id, payload)


@router.get("/{contract_id}/annexes/{annex_id}", response_model=ContractAnnexResponse)
def get_contract_annex(
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).get(contract_id, annex_id)


@router.put("/{contract_id}/annexes/{annex_id}", response_model=ContractAnnexResponse)
def update_contract_annex(
    payload: ContractAnnexUpdate,
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).update(contract_id, annex_id, payload)


@router.delete("/{contract_id}/annexes/{annex_id}", status_code=204)
def delete_contract_annex(
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    ContractAnnexService(db).delete(contract_id, annex_id)


# ── Contract Annex Items (ContractAnnexItem belongs to a ContractAnnex) ─────

@router.post(
    "/{contract_id}/annexes/{annex_id}/items",
    response_model=AnnexItemResponse,
    status_code=201,
)
def add_contract_annex_item(
    payload: AnnexItemCreate,
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).add_item(contract_id, annex_id, payload)


@router.put(
    "/{contract_id}/annexes/{annex_id}/items/{item_id}",
    response_model=AnnexItemResponse,
)
def update_contract_annex_item(
    payload: AnnexItemUpdate,
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    item_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).update_item(contract_id, annex_id, item_id, payload)


@router.delete("/{contract_id}/annexes/{annex_id}/items/{item_id}", status_code=204)
def delete_contract_annex_item(
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    item_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    ContractAnnexService(db).delete_item(contract_id, annex_id, item_id)


@router.post("/external", response_model=ContractResponse, status_code=201)
def create_external_contract(
    payload: ExternalContractCreateRequest,
    db: Session = Depends(get_db),
    # Здесь можно добавить зависимость проверки API-ключа внешнего сайта:
    # api_key: str = Security(verify_external_api_key)
):
    """
    Открытое/защищенное API для внешнего сайта: 
    создает правообладателя (при необходимости), договор (draft), папку и документ.
    """
    service = ContractService(db)
    return service.create_external_contract(payload)


@router.post("/external/annex", response_model=ContractAnnexResponse, status_code=201)
def create_external_annex(
    payload: IncomingAnnexPayload,
    db: Session = Depends(get_db),
    # Здесь можно добавить зависимость проверки API-ключа внешнего сайта:
    # api_key: str = Security(verify_external_api_key)
):
    """
    Открытое/защищенное API для внешнего сайта: создает приложение (Annex) и
    его строки (ContractAnnexItem) к уже существующему договору, а также
    генерирует .xlsx документ приложения в папке договора.
    """
    service = ContractAnnexService(db)
    return service.create_external_annex(payload)