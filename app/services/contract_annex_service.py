"""ContractAnnexService — business logic for the Contract Annex module."""
from __future__ import annotations

from sqlite3 import IntegrityError
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from __crud.contract_annex_repository import AnnexNumberConflictError, ContractAnnexRepository
from __crud.contract_repository import ContractRepository
from __schemas.contract_annex import (
    AnnexItemCreate,
    AnnexItemResponse,
    AnnexItemUpdate,
    ContractAnnexCreate,
    ContractAnnexListItem,
    ContractAnnexResponse,
    ContractAnnexUpdate,
    IncomingAnnexPayload,
)
from models import AnnexStatus

from .document_service import DocumentService


class ContractAnnexService:
    def __init__(self, db: Session):
        self.db = db
        self.contract_repo = ContractRepository(db)
        self.annex_repo = ContractAnnexRepository(db)

    @staticmethod
    def _to_response(annex) -> ContractAnnexResponse:
        return ContractAnnexResponse.model_validate(annex)

    def _get_owned_annex(self, contract_id: int, annex_id: int):
        """Loads the annex and makes sure it actually belongs to `contract_id`,
        so a route like /contracts/{contract_id}/annexes/{annex_id} can't be
        used to reach an annex that belongs to a different contract.
        """
        annex = self.annex_repo.get_by_id(annex_id)
        if annex is None or annex.contract_id != contract_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приложение не найдено")
        return annex

    def list_by_contract(
        self,
        contract_id: int,
        *,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContractAnnexListItem], int]:
        if self.contract_repo.get_by_id(contract_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        annexes, total, counts = self.annex_repo.list_by_contract(
            contract_id, search=search, sort_by=sort_by, sort_dir=sort_dir, limit=limit, offset=offset
        )
        items = [
            ContractAnnexListItem(
                id=a.id,
                contract_id=a.contract_id,
                annex_number=a.annex_number,
                doc_date=a.doc_date,
                status=a.status,
                file_path=a.file_path,
                items_count=counts.get(a.id, 0),
            )
            for a in annexes
        ]
        return items, total

    def get(self, contract_id: int, annex_id: int) -> ContractAnnexResponse:
        annex = self._get_owned_annex(contract_id, annex_id)
        return self._to_response(annex)

    def create(self, contract_id: int, payload: ContractAnnexCreate) -> ContractAnnexResponse:
        contract = self.contract_repo.get_by_id(contract_id)
        if contract is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        holder = contract.right_holder
        if holder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Правообладатель не найден")

        annex_data = {
            "contract_id": contract_id,
            "annex_number": payload.annex_number,
            "doc_date": payload.doc_date,
            "status": AnnexStatus(payload.status.value),
            "payload_snapshot": payload.model_dump(mode="json"),
        }
        items_data = [item.model_dump() for item in payload.items]

        try:
            annex = self.annex_repo.create_with_items(annex_data, items_data)
        except AnnexNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Приложение с таким номером уже существует для данного договора",
            ) from e
        try:
            file_path = DocumentService.generate_annex_doc(
                contract=contract,
                holder=holder,
                annex=annex,
            )
            annex = self.annex_repo.set_status(annex, AnnexStatus.PARSED, file_path=file_path)
        except Exception as exc:
            self.annex_repo.set_status(annex, AnnexStatus.FAILED)
            error_msg = f"Приложение успешно сохранено в БД (ID: {annex.id}), но не удалось сгенерировать файл Excel: {exc}"
            print(f"🔥 {error_msg}", flush=True)
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            ) from exc

        return self._to_response(annex)

    def update(self, contract_id: int, annex_id: int, payload: ContractAnnexUpdate) -> ContractAnnexResponse:
        annex = self._get_owned_annex(contract_id, annex_id)

        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] is not None:
            data["status"] = AnnexStatus(data["status"].value if hasattr(data["status"], "value") else data["status"])

        try:
            annex = self.annex_repo.update(annex_id, data)
        except AnnexNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Приложение с таким номером уже существует для данного договора",
            ) from e

        # Перегенерация файла приложения с учетом новых данных (номер, дата, строки)
        contract = self.contract_repo.get_by_id(contract_id)
        holder = contract.right_holder if contract else None
        if contract is not None and holder is not None:
            try:
                file_path = DocumentService.generate_annex_doc(
                    contract=contract,
                    holder=holder,
                    annex=annex,
                )
                annex = self.annex_repo.set_status(annex, annex.status, file_path=file_path)
            except Exception as exc:
                print(f"⚠️ Не удалось перегенерировать файл приложения: {exc}", flush=True)

        return self._to_response(annex)

    def delete(self, contract_id: int) -> None:
        obj = self.repo.get_by_id(contract_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        holder = obj.right_holder

        # Сохраняем пути к файлам приложений перед удалением записей из БД
        annex_file_paths = [annex.file_path for annex in obj.annexes if annex.file_path]

        try:
            # 1. Удаляем запись договора из БД (приложения удалятся каскадно)
            deleted = self.repo.delete(contract_id)
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор используется в других данных и не может быть удалён",
            ) from e

        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        # 2. Точечно удаляем ТОЛЬКО файлы этого договора и его приложений
        if holder:
            try:
                from pathlib import Path
                contract_dir = DocumentService._get_contract_dir(obj, holder)
                
                # Удаляем строго файл самого договора (.docx)
                contract_file = contract_dir / f"Договор_{obj.contract_number}.docx"
                if contract_file.exists():
                    contract_file.unlink(missing_ok=True)
                    print(f"🗑️ Удален файл договора: {contract_file}", flush=True)

                # Удаляем файлы приложений (.xlsx)
                for path_str in annex_file_paths:
                    if path_str:
                        annex_file = Path(path_str)
                        if annex_file.exists():
                            annex_file.unlink(missing_ok=True)
                            print(f"🗑️ Удален файл приложения: {annex_file}", flush=True)

            except Exception as exc:
                print(f"⚠️ Ошибка при удалении файлов договора/приложений: {exc}", flush=True)

    # ── ContractAnnexItem CRUD ──────────────────────────────────────────────

    
    def add_item(self, contract_id: int, annex_id: int, payload: AnnexItemCreate) -> AnnexItemResponse:
        self._get_owned_annex(contract_id, annex_id)
        item = self.annex_repo.add_item(annex_id, payload.model_dump())
        return AnnexItemResponse.model_validate(item)

    def update_item(
        self, contract_id: int, annex_id: int, item_id: int, payload: AnnexItemUpdate
    ) -> AnnexItemResponse:
        self._get_owned_annex(contract_id, annex_id)
        data = payload.model_dump(exclude_unset=True)
        item = self.annex_repo.update_item(annex_id, item_id, data)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Произведение не найдено")
        return AnnexItemResponse.model_validate(item)

    def delete_item(self, contract_id: int, annex_id: int, item_id: int) -> None:
        self._get_owned_annex(contract_id, annex_id)
        deleted = self.annex_repo.delete_item(annex_id, item_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Произведение не найдено")

    def create_external_annex(self, payload: IncomingAnnexPayload) -> ContractAnnexResponse:
        """
        Принимает приложение (Annex) к уже существующему договору: сохраняет
        ContractAnnex + ContractAnnexItem в БД и генерирует .xlsx документ
        приложения в папке договора.
        """
        contract = self.contract_repo.get_by_number(payload.contract_number)
        if contract is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Договор с номером '{payload.contract_number}' не найден",
            )

        holder = contract.right_holder
        if holder is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="У договора не найден правообладатель",
            )

        annex_data = {
            "contract_id": contract.id,
            "annex_number": payload.annex_number,
            "doc_date": payload.doc_date,
            "status": AnnexStatus.PROCESSING,
            "payload_snapshot": payload.model_dump(mode="json"),
        }
        items_data = [item.model_dump() for item in payload.items]

        try:
            annex = self.annex_repo.create_with_items(annex_data, items_data)
        except AnnexNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Приложение с таким номером уже существует для данного договора",
            ) from e

        try:
            file_path = DocumentService.generate_annex_doc(
                contract=contract,
                holder=holder,
                annex=annex,
            )
        except Exception as exc:
            self.annex_repo.set_status(annex, AnnexStatus.FAILED)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Не удалось сгенерировать документ приложения: {exc}",
            ) from exc

        annex = self.annex_repo.set_status(annex, AnnexStatus.PARSED, file_path=file_path)
        return self._to_response(annex)
