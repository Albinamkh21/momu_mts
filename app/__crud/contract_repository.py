"""ContractRepository — DB access for the `contract` table (Contract module)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, Session

from models import Contract


class ContractNumberConflictError(Exception):
    """Raised when a contract with the same contract_number already exists."""


class ContractRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, contract_id: int) -> Optional[Contract]:
        return (
            self.db.query(Contract)
            .options(joinedload(Contract.right_holder))
            .filter(Contract.id == contract_id)
            .first()
        )

    def get_all(
        self,
        *,
        right_holder_id: Optional[int] = None,
        status: Optional[str] = None,
        direction_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Contract], int]:
        query = self.db.query(Contract).options(joinedload(Contract.right_holder))

        if right_holder_id is not None:
            query = query.filter(Contract.right_holder_id == right_holder_id)
        if status is not None:
            query = query.filter(Contract.status == status)
        if direction_type is not None:
            query = query.filter(Contract.direction_type == direction_type)
        if search:
            query = query.filter(Contract.contract_number.ilike(f"%{search}%"))

        total = query.count()
        items = query.order_by(Contract.id.desc()).offset(offset).limit(limit).all()
        return items, total

    def create(self, data: dict[str, Any]) -> Contract:
        obj = Contract(**data)
        self.db.add(obj)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ContractNumberConflictError(str(exc)) from exc
        self.db.refresh(obj)
        return obj

    def update(self, contract_id: int, data: dict[str, Any]) -> Optional[Contract]:
        obj = self.get_by_id(contract_id)
        if not obj:
            return None

        for key, value in data.items():
            setattr(obj, key, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ContractNumberConflictError(str(exc)) from exc
        self.db.refresh(obj)
        return obj

    def delete(self, contract_id: int) -> bool:
        obj = self.get_by_id(contract_id)
        if not obj:
            return False
        self.db.delete(obj)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise
        return True
