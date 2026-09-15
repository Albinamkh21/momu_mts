"""Controller (routes) for the RightHolder module.

Endpoint -> Controller (this router) -> RightsHolderService -> RightHolderRepository -> DB
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from __schemas.rights_holders import (
    RightsHolderCreate,
    RightsHolderListResponse,
    RightsHolderResponse,
    RightsHolderType,
    RightsHolderUpdate,
)
from services.rights_holder_service import RightsHolderService

router = APIRouter()


@router.get("", response_model=RightsHolderListResponse)
def list_rights_holders(
    search: Optional[str] = Query(None, max_length=255, description="Поиск по имени/псевдониму/ИИН-БИН"),
    type: Optional[RightsHolderType] = Query(None, description="Фильтр по типу правообладателя"),
    label_id: Optional[int] = Query(None, gt=0),
    alias: Optional[str] = Query(None, max_length=255, description="Фильтр по псевдониму"),
    sort_by: Optional[str] = Query(None, description="Поле сортировки"),
    sort_dir: str = Query("asc", description="Направление сортировки: asc или desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = RightsHolderService(db)
    items, total = service.list(
        search=search,
        type_=type,
        label_id=label_id,
        alias=alias,
        sort_by=sort_by,
        sort_dir=sort_dir if sort_dir == "desc" else "asc",
        limit=limit,
        offset=offset,
    )
    return RightsHolderListResponse(items=items, total=total)


@router.get("/{right_holder_id}", response_model=RightsHolderResponse)
def get_rights_holder(
    right_holder_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return RightsHolderService(db).get(right_holder_id)


@router.post("", response_model=RightsHolderResponse, status_code=201)
def create_rights_holder(
    payload: RightsHolderCreate,
    db: Session = Depends(get_db),
):
    return RightsHolderService(db).create(payload)


@router.put("/{right_holder_id}", response_model=RightsHolderResponse)
def update_rights_holder(
    payload: RightsHolderUpdate,
    right_holder_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return RightsHolderService(db).update(right_holder_id, payload)


@router.delete("/{right_holder_id}", status_code=204)
def delete_rights_holder(
    right_holder_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    RightsHolderService(db).delete(right_holder_id)
