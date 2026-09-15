"""RightHolderRepository — DB access for the `right_holder` table (Contract module)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import RightHolder

# Whitelisted sort columns to avoid arbitrary ORDER BY injection from client input.
SORTABLE_COLUMNS = {
    "id": RightHolder.id,
    "name": RightHolder.name,
    "type": RightHolder.type,
    "alias": RightHolder.alias,
    "iin_bin": RightHolder.iin_bin,
    "email": RightHolder.email,
    "phone": RightHolder.phone,
}


class RightHolderNameConflictError(Exception):
    """Raised when a right holder with the same name already exists."""


class RightHolderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, right_holder_id: int) -> Optional[RightHolder]:
        return self.db.get(RightHolder, right_holder_id)

    def get_by_name(self, name: str) -> Optional[RightHolder]:
        return self.db.query(RightHolder).filter(func.lower(RightHolder.name) == name.lower()).first()

    def get_all(
        self,
        *,
        search: Optional[str] = None,
        type_: Optional[str] = None,
        label_id: Optional[int] = None,
        alias: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RightHolder], int]:
        query = self.db.query(RightHolder)

        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    RightHolder.name.ilike(like),
                    RightHolder.alias.ilike(like),
                    RightHolder.full_name.ilike(like),
                    RightHolder.company_name.ilike(like),
                    RightHolder.iin_bin.ilike(like),
                )
            )
        if type_ is not None:
            query = query.filter(RightHolder.type == type_)
        if label_id is not None:
            query = query.filter(RightHolder.label_id == label_id)
        if alias:
            query = query.filter(RightHolder.alias.ilike(f"%{alias}%"))

        total = query.count()
        order_column = SORTABLE_COLUMNS.get(sort_by, RightHolder.name)
        order_clause = order_column.desc() if sort_dir == "desc" else order_column.asc()
        items = query.order_by(order_clause).offset(offset).limit(limit).all()
        return items, total

    def create(self, data: dict[str, Any]) -> RightHolder:
        obj = RightHolder(**data)
        self.db.add(obj)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RightHolderNameConflictError(str(exc)) from exc
        self.db.refresh(obj)
        return obj

    def update(self, right_holder_id: int, data: dict[str, Any]) -> Optional[RightHolder]:
        obj = self.get_by_id(right_holder_id)
        if not obj:
            return None

        for key, value in data.items():
            setattr(obj, key, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RightHolderNameConflictError(str(exc)) from exc
        self.db.refresh(obj)
        return obj

    def delete(self, right_holder_id: int) -> bool:
        obj = self.get_by_id(right_holder_id)
        if not obj:
            return False
        self.db.delete(obj)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise
        return True
