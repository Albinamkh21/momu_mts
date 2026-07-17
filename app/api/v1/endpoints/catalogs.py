from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import shutil
import os
from uuid import uuid4
from tasks.catalog_tasks import export_normalized_catalog_to_flat, delete_data_from_all_dictionaries_by_label
from tasks.catalog_tasks_v2 import sync_catalog_dictionaries 
from pydantic import BaseModel
router = APIRouter()

STORAGE_DIR = "/app/storage"
class DownloadRequest(BaseModel):
    label_id: int | None = None
    right_usage_type_id: int | None = None
    export_format: str | None = None




@router.post("/download")
async def download_catalog(request: DownloadRequest):
    # Передаём директорию назначения; имя файла генерируется автоматически в задаче
    task_result = export_normalized_catalog_to_flat.delay(
        "/app/storage",
        request.label_id,
        request.right_usage_type_id,
        request.export_format
    )

    return {
        "message": "Запущен процесс экспорта каталога",
        "task_id": task_result.id,
        "label_id": request.label_id,
        "right_usage_type_id": request.right_usage_type_id,
        "export_format": request.export_format
    }


@router.delete("/label/{label_id}")
async def delete_label_data(label_id: int):
    """Удаляет все данные о треках и связях для указанного лейбла."""
    print(f"Запуск удаления данных для label_id: {label_id}")
    task_result = delete_data_from_all_dictionaries_by_label.delay(label_id)

    return {
        "message": "Запущен процесс удаления данных по лейблу",
        "task_id": task_result.id,
        "label_id": label_id
    }
