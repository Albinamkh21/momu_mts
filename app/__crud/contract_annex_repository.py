"""ContractAnnexRepository — DB access for `contract_annex` / `contract_annex_items` tables."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models import ContractAnnex, ContractAnnexItem


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

    def set_status(self, annex: ContractAnnex, status, file_path: Optional[str] = None) -> ContractAnnex:
        annex.status = status
        if file_path is not None:
            annex.file_path = file_path
        self.db.commit()
        self.db.refresh(annex)
        return annex
