"""RightsHolderService — business logic for the RightHolder module."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from __crud.right_holder_repository import RightHolderNameConflictError, RightHolderRepository
from __schemas.rights_holders import RightsHolderCreate, RightsHolderResponse, RightsHolderUpdate


class RightsHolderService:
    def __init__(self, db: Session):
        self.repo = RightHolderRepository(db)

    def list(
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
    ) -> tuple[list[RightsHolderResponse], int]:
        items, total = self.repo.get_all(
            search=search,
            type_=type_,
            label_id=label_id,
            alias=alias,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
        return [RightsHolderResponse.model_validate(item) for item in items], total

    def get(self, right_holder_id: int) -> RightsHolderResponse:
        obj = self.repo.get_by_id(right_holder_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Правообладатель не найден")
        return RightsHolderResponse.model_validate(obj)

    def create(self, payload: RightsHolderCreate) -> RightsHolderResponse:
        data = payload.model_dump(exclude_none=True)
        try:
            obj = self.repo.create(data)
        except RightHolderNameConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Правообладатель с таким именем уже существует",
            ) from e
        return RightsHolderResponse.model_validate(obj)

    def update(self, right_holder_id: int, payload: RightsHolderUpdate) -> RightsHolderResponse:
        data = payload.model_dump(exclude_unset=True)
        try:
            obj = self.repo.update(right_holder_id, data)
        except RightHolderNameConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Правообладатель с таким именем уже существует",
            ) from e
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Правообладатель не найден")
        return RightsHolderResponse.model_validate(obj)

    def delete(self, right_holder_id: int) -> None:
        try:
            deleted = self.repo.delete(right_holder_id)
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Правообладатель используется в договорах/каталоге и не может быть удалён",
            ) from e
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Правообладатель не найден")
