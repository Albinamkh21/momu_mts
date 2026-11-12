"""ContractService — business logic for the Contract module."""
from __future__ import annotations

from asyncio.log import logger
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from __schemas.external_contract import ExternalContractCreateRequest
from .document_service import DocumentService   

from __crud.contract_repository import ContractNumberConflictError, ContractRepository
from __crud.right_holder_repository import RightHolderRepository
from __schemas.contracts import ContractCreate, ContractResponse, ContractUpdate


class ContractService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ContractRepository(db)
        self.right_holder_repo = RightHolderRepository(db)
        self.contract_repo = ContractRepository(db)

    @staticmethod
    def _to_response(obj) -> ContractResponse:
        return ContractResponse(
            id=obj.id,
            rights_holder_id=obj.right_holder_id,
            right_holder_name=obj.right_holder.name if obj.right_holder else None,
            contract_number=obj.contract_number,
            signed_date=obj.signed_date,
            valid_from=obj.valid_from,
            valid_to=obj.valid_to,
            status=obj.status,
            direction_type=obj.direction_type,
        )

    def list(
        self,
        *,
        right_holder_id: Optional[int] = None,
        status_: Optional[str] = None,
        direction_type: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContractResponse], int]:
        items, total = self.repo.get_all(
            right_holder_id=right_holder_id,
            status=status_,
            direction_type=direction_type,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
        return [self._to_response(item) for item in items], total

    def get(self, contract_id: int) -> ContractResponse:
        obj = self.repo.get_by_id(contract_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")
        return self._to_response(obj)

    def create(self, payload: ContractCreate) -> ContractResponse:
        if self.right_holder_repo.get_by_id(payload.rights_holder_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Правообладатель не найден",
            )

        data = payload.model_dump(exclude={"rights_holder_id"})
        data["right_holder_id"] = payload.rights_holder_id
        try:
            obj = self.repo.create(data)
        except ContractNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор с таким номером уже существует",
            ) from e
        return self._to_response(obj)

    def update(self, contract_id: int, payload: ContractUpdate) -> ContractResponse:
        data = payload.model_dump(exclude_unset=True)
        try:
            obj = self.repo.update(contract_id, data)
        except ContractNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор с таким номером уже существует",
            ) from e
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")
        return self._to_response(obj)

    def delete(self, contract_id: int) -> None:
        try:
            deleted = self.repo.delete(contract_id)
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор используется в других данных и не может быть удалён",
            ) from e
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")


    def create_external_contract(self, payload):
        try:
            # 1. Ищем или создаем правообладателя
            holder = None
            if payload.iin_bin:
                holder = self.right_holder_repo.get_by_iin(payload.iin_bin)

            holder_data = {
                "name": payload.name,
                "type": payload.type,
                "alias": payload.alias,
                "email": payload.email,
                "phone": payload.phone,
                "address": payload.address,
                "iin_bin": payload.iin_bin,
                "full_name": payload.full_name,
                "id_document_type": payload.id_document_type,
                "id_document_number": payload.id_document_number,
                "id_document_issued_by": payload.id_document_issued_by,
                "id_document_issue_date": payload.id_document_issue_date,
                "company_name": payload.company_name,
                "director_name": payload.director_name,
                "acting_basis": payload.acting_basis,
                "iban": payload.iban,
                "bank_name": payload.bank_name,
                "bik": payload.bik,
            }

            if holder:
                holder = self.right_holder_repo.update(holder.id, holder_data)
            else:
                holder = self.right_holder_repo.create(holder_data)

            # 2. Создаем договор (direction_type приводим к верхнему регистру для CHECK constraint)
            contract_data = {
                "contract_number": payload.contract_number,
                "right_holder_id": holder.id,
                "direction_type": payload.direction_type.upper() if payload.direction_type else None,
                "signed_date": payload.signed_date,
                "valid_from": payload.valid_from,
                "valid_to": payload.valid_to,
                "status": "DRAFT",
            }

            contract = self.contract_repo.create(contract_data)

            DocumentService.generate_contract_doc(
                contract=contract, 
                holder=holder, 
                payload_extra=payload.model_dump()
            )
            
            # Возвращаем сам объект контракта для валидации по response_model (ContractResponse)
            return contract

        except Exception as e:
            self.db.rollback()
            print(f"🔥 DB SAVE ERROR: {type(e).__name__}: {e}", flush=True)
            raise
