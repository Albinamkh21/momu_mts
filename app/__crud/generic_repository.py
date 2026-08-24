"""GenericRepository — CRUD + pagination/search for any registered dictionary model."""
from __future__ import annotations

from typing import Any, Optional, Type

from sqlalchemy import or_
from sqlalchemy.orm import Session


class GenericRepository:
    def __init__(self, db: Session, model: Type, search_fields: tuple[str, ...] = (), order_by: str = "id"):
        self.db = db
        self.model = model
        self.search_fields = search_fields
        self.order_by = order_by

    def get_all(self, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> tuple[list, int]:
        query = self.db.query(self.model)

        if search:
            conditions = [
                getattr(self.model, f).ilike(f"%{search}%")
                for f in self.search_fields
                if hasattr(self.model, f)
            ]
            if conditions:
                query = query.filter(or_(*conditions))

        total = query.count()

        order_col = getattr(self.model, self.order_by, None)
        if order_col is not None:
            query = query.order_by(order_col)

        items = query.offset(offset).limit(limit).all()
        return items, total

    def get_one(self, item_id: int):
        return self.db.get(self.model, item_id)

    def create(self, data: dict[str, Any]):
        obj = self.model(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, item_id: int, data: dict[str, Any]):
        obj = self.get_one(item_id)
        if obj is None:
            return None
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, item_id: int) -> bool:
        obj = self.get_one(item_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
