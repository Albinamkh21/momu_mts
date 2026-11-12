"""ContractAnnexRepository — DB access for `contract_annex` / `contract_annex_items` tables."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models import ContractAnnex, ContractAnnexItem

# Whitelisted sort columns to avoid arbitrary ORDER BY injection from client input.
SORTABLE_COLUMNS = {
    "id": ContractAnnex.id,
    "annex_number": ContractAnnex.annex_number,
    "doc_date": ContractAnnex.doc_date,
    "status": ContractAnnex.status,
}


class AnnexNumberConflictError(Exception):
    """Raised when an annex with the same number already exists for the contract."""


class ContractAnnexRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, annex_id: int) -> Optional[ContractAnnex]:
        return (
            self.db.query(ContractAnnex)
            .options(joinedload(ContractAnnex.items))
            .filter(ContractAnnex.id == annex_id)
            .first()
        )

    def get_by_contract_and_number(self, contract_id: int, annex_number: str) -> Optional[ContractAnnex]:
        return (
            self.db.query(ContractAnnex)
            .filter(
                ContractAnnex.contract_id == contract_id,
                ContractAnnex.annex_number == annex_number,
            )
            .first()
        )

    def list_by_contract(
        self,
        contract_id: int,
        *,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContractAnnex], int, dict[int, int]]:
        """Returns annexes for a contract (without eagerly loading items — a
        joinedload on the one-to-many `items` relation would inflate `.count()`),
        together with a {annex_id: items_count} map for the list view.
        """
        query = self.db.query(ContractAnnex).filter(ContractAnnex.contract_id == contract_id)
        if search:
            query = query.filter(ContractAnnex.annex_number.ilike(f"%{search}%"))
        total = query.count()

        order_column = SORTABLE_COLUMNS.get(sort_by, ContractAnnex.doc_date)
        order_clause = order_column.desc() if sort_dir == "desc" else order_column.asc()
        annexes = query.order_by(order_clause).offset(offset).limit(limit).all()

        counts: dict[int, int] = {}
        if annexes:
            annex_ids = [a.id for a in annexes]
            counts = dict(
                self.db.query(ContractAnnexItem.annex_id, func.count(ContractAnnexItem.id))
                .filter(ContractAnnexItem.annex_id.in_(annex_ids))
                .group_by(ContractAnnexItem.annex_id)
                .all()
            )
        return annexes, total, counts

    def create_with_items(
        self,
        annex_data: dict[str, Any],
        items_data: list[dict[str, Any]],
    ) -> ContractAnnex:
        """Creates a ContractAnnex together with its ContractAnnexItem rows in one transaction."""
        annex = ContractAnnex(**annex_data)
        annex.items = [ContractAnnexItem(**item) for item in items_data]

        self.db.add(annex)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AnnexNumberConflictError(str(exc)) from exc
        self.db.refresh(annex)
        return annex

    def update(self, annex_id: int, data: dict[str, Any]) -> Optional[ContractAnnex]:
        annex = self.get_by_id(annex_id)
        if not annex:
            return None

        for key, value in data.items():
            setattr(annex, key, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AnnexNumberConflictError(str(exc)) from exc
        self.db.refresh(annex)
        return annex

    def delete(self, annex_id: int) -> bool:
        annex = self.get_by_id(annex_id)
        if not annex:
            return False
        self.db.delete(annex)
        self.db.commit()
        return True

    def set_status(self, annex: ContractAnnex, status, file_path: Optional[str] = None) -> ContractAnnex:
        annex.status = status
        if file_path is not None:
            annex.file_path = file_path
        self.db.commit()
        self.db.refresh(annex)
        return annex

    # ── ContractAnnexItem CRUD ──────────────────────────────────────────────

    def get_item(self, annex_id: int, item_id: int) -> Optional[ContractAnnexItem]:
        return (
            self.db.query(ContractAnnexItem)
            .filter(ContractAnnexItem.id == item_id, ContractAnnexItem.annex_id == annex_id)
            .first()
        )

    def add_item(self, annex_id: int, item_data: dict[str, Any]) -> ContractAnnexItem:
        next_line_number = (
            self.db.query(func.coalesce(func.max(ContractAnnexItem.line_number), 0))
            .filter(ContractAnnexItem.annex_id == annex_id)
            .scalar()
        ) + 1
        item = ContractAnnexItem(annex_id=annex_id, line_number=next_line_number, **item_data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(self, annex_id: int, item_id: int, data: dict[str, Any]) -> Optional[ContractAnnexItem]:
        item = self.get_item(annex_id, item_id)
        if not item:
            return None
        for key, value in data.items():
            setattr(item, key, value)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_item(self, annex_id: int, item_id: int) -> bool:
        item = self.get_item(annex_id, item_id)
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

