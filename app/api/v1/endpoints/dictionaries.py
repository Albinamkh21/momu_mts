"""Factory Controller — single set of REST routes for every registered dictionary."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from services.dictionary_service import DictionaryService

router = APIRouter()


@router.get("/{dict_key}")
def list_items(
    dict_key: str,
    search: Optional[str] = Query(None, description="Глобальный поиск по справочнику"),
    limit: int = Query(50, le=500, ge=1),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return DictionaryService(db, dict_key).list(search, limit, offset)


@router.get("/{dict_key}/{item_id}")
def get_item(dict_key: str, item_id: int, db: Session = Depends(get_db)):
    return DictionaryService(db, dict_key).get(item_id)


@router.post("/{dict_key}", status_code=201)
def create_item(dict_key: str, payload: dict[str, Any], db: Session = Depends(get_db)):
    return DictionaryService(db, dict_key).create(payload)


@router.put("/{dict_key}/{item_id}")
def update_item(dict_key: str, item_id: int, payload: dict[str, Any], db: Session = Depends(get_db)):
    return DictionaryService(db, dict_key).update(item_id, payload)


@router.delete("/{dict_key}/{item_id}", status_code=204)
def delete_item(dict_key: str, item_id: int, db: Session = Depends(get_db)):
    DictionaryService(db, dict_key).delete(item_id)
