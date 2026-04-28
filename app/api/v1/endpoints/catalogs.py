from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import shutil
import os
from uuid import uuid4
from celery import chain
from tasks.catalog_tasks import process_catalog_file,  check_catalog_integrity, export_normalized_catalog_to_flat, delete_data_from_all_dictionaries_by_label
from tasks.catalog_tasks_v2 import  sync_catalog_dictionaries 
from tasks.report_tasks import update_catalog_dictionaries_from_report
from pydantic import BaseModel
router = APIRouter()

STORAGE_DIR = "/app/storage"
class DownloadRequest(BaseModel):
    label_id: int | None = None

@router.post("/upload")
async def upload_catalog(file: UploadFile = File(...)):
    # Проверяем расширение
    if not file.filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    # Создаем уникальное имя, чтобы файлы не перезаписывались
    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    # Сохраняем файл на диск
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    userId = "albina"
    workflow = chain(
        process_catalog_file.s(file_path, userId, file.filename),
        sync_catalog_dictionaries.s("v1"),
      
    )
 
    task_result = workflow.apply_async()


    #task_result = sync_catalog_dictionaries.delay()

    return {
        "message": "Файл принят и поставлен в очередь на обработку",
        "task_id": task_result.id,
        "filename": file.filename
    }


@router.get("/check_upload_catalog")
async def check_upload_catalog():
    """Проверяет целостность загрузки каталога: ищет потери между staging и справочниками."""
    report = check_catalog_integrity()

    summary = []
    for table_name, info in report.items():
        if info.get("ok"):
            line = f"✅ {table_name}: всё на месте"
            if "staging_count" in info:
                line += f" (staging: {info['staging_count']}, target: {info['target_count']})"
        else:
            line = f"❌ {table_name}: "
            if "staging_count" in info and "target_count" in info:
                line += f"в staging {info['staging_count']}, в таблице {info['target_count']}"
            if "missing_count" in info and info["missing_count"] > 0:
                line += f", не хватает {info['missing_count']}"

        summary.append(line)

    return {
        "summary": summary,
        "details": report
    }


@router.post("/download")
async def download_catalog(request: DownloadRequest):
    # Передаём директорию назначения; имя файла генерируется автоматически в задаче
    task_result = export_normalized_catalog_to_flat.delay("/app/storage", request.label_id)

    return {
        "message": "Запущен процесс экспорта каталога",
        "task_id": task_result.id,
        "label_id": request.label_id
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
