"""ContractService — business logic for the Contract module."""
from __future__ import annotations

import os
import platform
import subprocess
from asyncio.log import logger
from pathlib import Path
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
            file_path=obj.file_path,
            file_name=obj.file_name,
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
        holder = self.right_holder_repo.get_by_id(payload.rights_holder_id)
        if holder is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Правообладатель не найден",
            )

        data = payload.model_dump(exclude={"rights_holder_id"})
        data["right_holder_id"] = holder.id
        try:
            obj = self.repo.create(data)
        except ContractNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор с таким номером уже существует",
            ) from e

        response_data = self._to_response(obj)

        # Генерация документа договора
        try:
            generated_path = DocumentService.generate_contract_doc(
                contract=obj,
                holder=holder,
                payload_extra=payload.model_dump(),
            )
            path_obj = Path(generated_path)
            obj = self.repo.update(
                obj.id,
                {"file_path": str(path_obj.parent), "file_name": path_obj.name},
            )
            response_data = self._to_response(obj)
        except Exception as exc:
            error_msg = f"Договор сохранен в БД (ID: {obj.id}), но не удалось сгенерировать файл документа: {exc}"
            print(f"⚠️ {error_msg}", flush=True)
            
            # Передаем предупреждение в ответ фронтенду/клиенту
            if hasattr(response_data, "warning"):
                response_data.warning = error_msg

        return response_data

    def update(self, contract_id: int, payload: ContractUpdate) -> ContractResponse:
        data = payload.model_dump(exclude_unset=True)

        existing = self.repo.get_by_id(contract_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")
        old_file_path, old_file_name = existing.file_path, existing.file_name

        try:
            obj = self.repo.update(contract_id, data)
        except ContractNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор с таким номером уже существует",
            ) from e
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        # Перегенерация файла договора с учетом новых данных
        holder = obj.right_holder
        if holder is not None:
            try:
                generated_path = DocumentService.generate_contract_doc(
                    contract=obj,
                    holder=holder,
                    payload_extra=data,
                )
                new_path_obj = Path(generated_path)
                obj = self.repo.update(
                    contract_id,
                    {"file_path": str(new_path_obj.parent), "file_name": new_path_obj.name},
                )

                # Если номер договора/правообладатель изменились и файл переехал
                # в другую папку — удаляем старый файл, чтобы не плодить копии.
                if old_file_path and old_file_name:
                    old_full_path = Path(old_file_path) / old_file_name
                    if old_full_path != new_path_obj and old_full_path.exists():
                        old_full_path.unlink(missing_ok=True)
            except Exception as exc:
                print(f"⚠️ Не удалось перегенерировать файл договора: {exc}", flush=True)

        return self._to_response(obj)

    def delete(self, contract_id: int) -> None:
        obj = self.repo.get_by_id(contract_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        holder = obj.right_holder

        # Собираем пути к файлам приложений ДО удаления записи из БД
        annex_file_paths = [annex.file_path for annex in obj.annexes if annex.file_path]

        try:
            # БД и SQLAlchemy сами каскадно удалят приложения и их строки
            deleted = self.repo.delete(contract_id)
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор используется в других связанных данных и не может быть удалён",
            ) from e

        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

 
        if holder:
            try:
                contract_dir = DocumentService._get_contract_dir(obj, holder)
                
                # 1. Удаляем файл договора (.docx)
                contract_file = contract_dir / f"Договор_{obj.contract_number}.docx"
                if contract_file.exists():
                    contract_file.unlink(missing_ok=True)
                    print(f"🗑️ Удален файл договора: {contract_file}", flush=True)

                # 2. Удаляем файлы приложений (.xlsx)
                for path_str in annex_file_paths:
                    if path_str:
                        annex_file = Path(path_str)
                        if annex_file.exists():
                            annex_file.unlink(missing_ok=True)
                            print(f"🗑️ Удален файл приложения: {annex_file}", flush=True)

            except Exception as exc:
                print(f"⚠️ Ошибка при удалении файлов с диска: {exc}", flush=True)

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

            generated_path = DocumentService.generate_contract_doc(
                contract=contract, 
                holder=holder, 
                payload_extra=payload.model_dump()
            )
            path_obj = Path(generated_path)
            contract = self.contract_repo.update(
                contract.id,
                {"file_path": str(path_obj.parent), "file_name": path_obj.name},
            )
            
            # Возвращаем сам объект контракта для валидации по response_model (ContractResponse)
            return contract

        except Exception as e:
            self.db.rollback()
            print(f"🔥 DB SAVE ERROR: {type(e).__name__}: {e}", flush=True)
            raise

    def get_contract_file_path(self, contract_id: int) -> tuple[str, str]:
        obj = self.repo.get_by_id(contract_id)
        if obj is None or not obj.file_path or not obj.file_name:
            raise HTTPException(status_code=404, detail="Договор или файл не найден")

        target_path = os.path.join(obj.file_path, obj.file_name)
        if not os.path.exists(target_path):
            raise HTTPException(status_code=404, detail="Файл физически отсутствует на сервере")

        return target_path, obj.file_name