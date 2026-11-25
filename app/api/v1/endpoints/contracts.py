import os
import sys
from typing import Optional
from uuid import uuid4
import shutil

from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from openpyxl import Workbook

from celery import chain
from core.database import  create_engine, get_db


from __schemas.contract_annex import (
    AnnexItemCreate,
    AnnexItemResponse,
    AnnexItemUpdate,
    ContractAnnexCreate,
    ContractAnnexListResponse,
    ContractAnnexResponse,
    ContractAnnexUpdate,
    IncomingAnnexPayload,
)
from __schemas.contracts import (
    ContractCreate,
    ContractDirectionType,
    ContractListResponse,
    ContractResponse,
    ContractStatus,
    ContractUpdate,
)
from __schemas.external_contract import ExternalContractCreateRequest
from services.contract_annex_service import ContractAnnexService
from services.contract_service import ContractService
from tasks.contract_import_tasks import process_contract_file, sync_contracts_from_staging
from api.deps import get_current_user, User, Depends
from core.database import get_conn
from core.celery_app import celery_app


router = APIRouter()



def get_database_url():
    is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "true"
    
    if is_testing:
        test_url = os.getenv("DATABASE_URL_TEST")
        if test_url:
            return test_url
        # Если тест идет, а тестовой переменной нет — подставляем тестовую базу явно по шаблону
        return os.getenv("DATABASE_URL", "").replace("/momu", "/momu_test")
        
    return os.getenv("DATABASE_URL")

DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL)
STORAGE_DIR = "/app/storage"


@router.get("/download_export/{filename}")
async def download_file(filename: str):
    # Защита от path traversal – разрешаем только файлы из storage
    safe_path = os.path.join(STORAGE_DIR, os.path.basename(filename))
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(
        path=safe_path,
        filename=filename,
        media_type="application/octet-stream"
    )  


@router.get("", response_model=ContractListResponse)
def list_contracts(
    rights_holder_id: Optional[int] = Query(None, gt=0),
    status: Optional[ContractStatus] = Query(None),
    direction_type: Optional[ContractDirectionType] = Query(None),
    search: Optional[str] = Query(None, max_length=255, description="Поиск по номеру договора"),
    sort_by: Optional[str] = Query(None, description="Поле сортировки"),
    sort_dir: str = Query("desc", description="Направление сортировки: asc или desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = ContractService(db)
    items, total = service.list(
        right_holder_id=rights_holder_id,
        status_=status,
        direction_type=direction_type,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir if sort_dir == "asc" else "desc",
        limit=limit,
        offset=offset,
    )
    return ContractListResponse(items=items, total=total)


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractService(db).get(contract_id)


@router.post("", response_model=ContractResponse, status_code=201)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
):
    return ContractService(db).create(payload)


@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    payload: ContractUpdate,
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractService(db).update(contract_id, payload)


@router.delete("/{contract_id}", status_code=204)
def delete_contract(
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    ContractService(db).delete(contract_id)


# ── Contract Annexes (nested CRUD, ContractAnnex belongs to a Contract) ─────

@router.get("/{contract_id}/annexes", response_model=ContractAnnexListResponse)
def list_contract_annexes(
    contract_id: int = Path(..., gt=0),
    search: Optional[str] = Query(None, max_length=50, description="Поиск по номеру приложения"),
    sort_by: Optional[str] = Query(None, description="Поле сортировки"),
    sort_dir: str = Query("asc", description="Направление сортировки: asc или desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = ContractAnnexService(db)
    items, total = service.list_by_contract(
        contract_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir if sort_dir == "desc" else "asc",
        limit=limit,
        offset=offset,
    )
    return ContractAnnexListResponse(items=items, total=total)


@router.post("/{contract_id}/annexes", response_model=ContractAnnexResponse, status_code=201)
def create_contract_annex(
    payload: ContractAnnexCreate,
    contract_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).create(contract_id, payload)


@router.get("/{contract_id}/annexes/{annex_id}", response_model=ContractAnnexResponse)
def get_contract_annex(
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).get(contract_id, annex_id)


@router.put("/{contract_id}/annexes/{annex_id}", response_model=ContractAnnexResponse)
def update_contract_annex(
    payload: ContractAnnexUpdate,
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).update(contract_id, annex_id, payload)


@router.delete("/{contract_id}/annexes/{annex_id}", status_code=204)
def delete_contract_annex(
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    ContractAnnexService(db).delete(contract_id, annex_id)


# ── Contract Annex Items (ContractAnnexItem belongs to a ContractAnnex) ─────

@router.post(
    "/{contract_id}/annexes/{annex_id}/items",
    response_model=AnnexItemResponse,
    status_code=201,
)
def add_contract_annex_item(
    payload: AnnexItemCreate,
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).add_item(contract_id, annex_id, payload)


@router.put(
    "/{contract_id}/annexes/{annex_id}/items/{item_id}",
    response_model=AnnexItemResponse,
)
def update_contract_annex_item(
    payload: AnnexItemUpdate,
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    item_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return ContractAnnexService(db).update_item(contract_id, annex_id, item_id, payload)


@router.delete("/{contract_id}/annexes/{annex_id}/items/{item_id}", status_code=204)
def delete_contract_annex_item(
    contract_id: int = Path(..., gt=0),
    annex_id: int = Path(..., gt=0),
    item_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    ContractAnnexService(db).delete_item(contract_id, annex_id, item_id)


@router.post("/external", response_model=ContractResponse, status_code=201)
def create_external_contract(
    payload: ExternalContractCreateRequest,
    db: Session = Depends(get_db),
    # Здесь можно добавить зависимость проверки API-ключа внешнего сайта:
    # api_key: str = Security(verify_external_api_key)
):
    """
    Открытое/защищенное API для внешнего сайта: 
    создает правообладателя (при необходимости), договор (draft), папку и документ.
    """
    service = ContractService(db)
    return service.create_external_contract(payload)


@router.post("/external/annex", response_model=ContractAnnexResponse, status_code=201)
def create_external_annex(
    payload: IncomingAnnexPayload,
    db: Session = Depends(get_db),
    # Здесь можно добавить зависимость проверки API-ключа внешнего сайта:
    # api_key: str = Security(verify_external_api_key)
):
    """
    Открытое/защищенное API для внешнего сайта: создает приложение (Annex) и
    его строки (ContractAnnexItem) к уже существующему договору, а также
    генерирует .xlsx документ приложения в папке договора.
    """
    service = ContractAnnexService(db)
    return service.create_external_annex(payload)



@router.post("/{contract_id}/open-folder", status_code=200)
def open_contract_folder(
    contract_id: int,
    db: Session = Depends(get_db)
):
    """
    Открывает папку указанного договора на сервере/в системе.
    """
    service = ContractService(db) # (или как у вас называется класс сервиса для договоров)
    return service.open_folder(contract_id)


@router.get("/contracts/{contract_id}/download")
def download_contract(contract_id: int, db: Session = Depends(get_db)):
    service = ContractService(db)
    file_path, file_name = service.get_contract_file_path(contract_id)
    return FileResponse(file_path, filename=file_name)

@router.get("/{contract_id}/annexes/{annex_id}/download")
def download_contract_annex(
    contract_id: int, 
    annex_id: int, 
    db: Session = Depends(get_db)
):
    service = ContractAnnexService(db)
    file_path = service.get_annex_file_path(contract_id, annex_id)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    
    filename = os.path.basename(file_path)

    return FileResponse(file_path, filename=filename)

@router.post("/upload")
async def upload_contracts(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    if not file.filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    upload_id = str(uuid4())
    workflow = chain(
        process_contract_file.s(file_path, upload_id=upload_id, original_filename=file.filename,  user_id=current_user.id),
        sync_contracts_from_staging.s(upload_id=upload_id),
    )

  
    task_result = workflow.apply_async(task_id=upload_id)

    return {
        "message": "Файл принят и поставлен в очередь на обработку (v2)",
        "task_id": upload_id,
        "filename": file.filename
    }

@router.post("/export", status_code=200)
def export_contracts_excel(
    rights_holder_id: Optional[int] = Query(None, gt=0),
    status: Optional[str] = Query(None),
    direction_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=255),
    db: Session = Depends(get_db),
):
    # Преобразуем пустые строки в None, чтобы не ломать SQL-фильтры
    status_val = status if status and status.strip() else None
    direction_val = direction_type if direction_type and direction_type.strip() else None

    result = ContractService(db).export_to_excel(
        rights_holder_id=rights_holder_id,
        status=status_val,
        direction_type=direction_val,
        search=search,
        output_dir=STORAGE_DIR,
    )
    return {
        "status": "success",
        "filename": result["filename"],
        "rows_exported": result["rows_exported"],
    }


@router.post("/{contract_id}/upload-file")
def upload_contract_file(
    contract_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    contract = ContractService(db).repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not contract.file_path:
        raise HTTPException(status_code=400, detail="У договора не задана папка (file_path)")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")

    os.makedirs(contract.file_path, exist_ok=True)
    safe_filename = os.path.basename(file.filename)
    dest_path = os.path.join(contract.file_path, safe_filename)

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    return {
        "status": "success",
        "contract_id": contract_id,
        "filename": safe_filename,
        "file_path": dest_path,
    }

    
