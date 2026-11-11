"""ContractAnnexService — business logic for the Contract Annex module."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from __crud.contract_annex_repository import AnnexNumberConflictError, ContractAnnexRepository
from __crud.contract_repository import ContractRepository
from __schemas.contract_annex import ContractAnnexResponse, IncomingAnnexPayload
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
