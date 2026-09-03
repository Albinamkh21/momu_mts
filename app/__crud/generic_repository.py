"""GenericRepository — CRUD + pagination/search for any registered dictionary model."""
from __future__ import annotations

import logging
from typing import Any, Optional, Type, TypeVar

from sqlalchemy import inspect, or_, String
from sqlalchemy.orm import Session, with_parent

logger = logging.getLogger(__name__)

# Optional: TypeVar for better IDE autocomplete on returned models
T = TypeVar("T") 


class RecordInUseError(Exception):
    """Raised when a delete is blocked because other rows still reference this record."""
    def __init__(self, relationship_name: str):
        self.relationship_name = relationship_name
        super().__init__(f"Record is referenced via '{relationship_name}' and cannot be deleted")

class GenericRepository:
    def __init__(self, db: Session, model: Type[T], search_fields: tuple[str, ...] = (), order_by: str = "id"):
        self.db = db
        self.model = model
        self.search_fields = search_fields
        self.order_by = order_by

    def get_all(
        self,
        search: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[T], int]:
        query = self.db.query(self.model)
        logger.debug(f"[get_all] model={self.model.__name__}, search={search}, filters={filters}")

        # Global Search
        if search:
            conditions = [
                getattr(self.model, f).ilike(f"%{search}%")
                for f in self.search_fields
                if hasattr(self.model, f)
            ]
            if conditions:
                query = query.filter(or_(*conditions))
                logger.debug(f"[get_all] Applied global search, conditions count={len(conditions)}")

        # Exact vs Partial Filters
        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(self.model, field):
                    column = getattr(self.model, field)
                    
                    # If it's a string column, use ILIKE. Otherwise, use exact match (==)
                    if isinstance(column.type, String):
                        query = query.filter(column.ilike(f"%{value}%"))
                        logger.debug(f"[get_all] Applied string filter: {field} ILIKE '%{value}%'")
                    else:
                        query = query.filter(column == value)
                        logger.debug(f"[get_all] Applied exact filter: {field} == {value}")

        total = query.count()
        logger.debug(f"[get_all] After filters, total records={total}")

        order_col = getattr(self.model, self.order_by, None)
        if order_col is not None:
            query = query.order_by(order_col)

        items = query.offset(offset).limit(limit).all()
        return items, total

    def get_one(self, item_id: int) -> Optional[T]:
        return self.db.get(self.model, item_id)

    def create(self, data: dict[str, Any]) -> Any:
            obj = self.model(**data)
            self.db.add(obj)
            self.db.commit()      # Сохраняем в базу!
            self.db.refresh(obj)  # Обновляем объект, чтобы подтянулся ID и дефолтные поля
            return obj

    def update(self, item_id: int, data: dict[str, Any]) -> Optional[Any]:
        obj = self.get_one(item_id)
        if not obj:
            return None
            
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
                
        self.db.commit()      # Сохраняем изменения в базу!
        self.db.refresh(obj)
        return obj

    def delete(self, item_id: int) -> bool:
        obj = self.get_one(item_id)
        if not obj:
            return False

        blocking_relationship = self._find_blocking_relationship(obj)
        if blocking_relationship:
            raise RecordInUseError(blocking_relationship)

        self.db.delete(obj)
        self.db.commit()      # Удаляем из базы навсегда!
        return True

    def _find_blocking_relationship(self, obj: Any) -> Optional[str]:
        """Checks ORM relationships (not just the DB FK) so deletion is blocked even if the
        underlying constraint is missing/misconfigured on the actual database."""
        mapper = inspect(self.model)
        for rel in mapper.relationships:
            if not rel.uselist:
                continue  # skip many-to-one/one-to-one scalar refs; only collections mean "has data"
            related_attr = getattr(self.model, rel.key)
            has_related = self.db.query(
                self.db.query(rel.mapper.class_).filter(with_parent(obj, related_attr)).exists()
            ).scalar()
            if has_related:
                return rel.key
        return None