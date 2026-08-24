"""DictionaryService — Service Factory for the Generic Admin Engine.

Resolves a dict_key against the DICTIONARY_REGISTRY, builds a GenericRepository
for the matching model, and exposes plain-dict CRUD operations for the controller.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from __crud.generic_repository import GenericRepository
from core.dictionary_registry import get_dictionary_config


def _to_dict(obj: Any) -> dict[str, Any]:
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}


class DictionaryService:
    def __init__(self, db: Session, dict_key: str):
        config = get_dictionary_config(dict_key)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Справочник '{dict_key}' не найден",
            )
        self.config = config
        self.repo = GenericRepository(db, config.model, config.search_fields, config.order_by)

    def list(self, search: str | None, limit: int, offset: int) -> dict:
        items, total = self.repo.get_all(search=search, limit=limit, offset=offset)
        return {
            "items": [_to_dict(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get(self, item_id: int) -> dict:
        obj = self.repo.get_one(item_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
        return _to_dict(obj)

    def create(self, payload: dict[str, Any]) -> dict:
        data = self._strip_read_only(payload)
        try:
            obj = self.repo.create(data)
        except IntegrityError as e:
            self.repo.db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_integrity_error_message(e)) from e
        return _to_dict(obj)

    def update(self, item_id: int, payload: dict[str, Any]) -> dict:
        data = self._strip_read_only(payload)
        try:
            obj = self.repo.update(item_id, data)
        except IntegrityError as e:
            self.repo.db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_integrity_error_message(e)) from e
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
        return _to_dict(obj)

    def delete(self, item_id: int) -> None:
        try:
            deleted = self.repo.delete(item_id)
        except IntegrityError as e:
            self.repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Запись используется в других данных и не может быть удалена",
            ) from e
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")

    def _strip_read_only(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in payload.items() if k not in self.config.read_only_fields}


def _integrity_error_message(e: IntegrityError) -> str:
    return "Нарушение ограничения целостности данных (дублирующееся значение или неверная ссылка)"
