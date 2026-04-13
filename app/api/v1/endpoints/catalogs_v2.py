from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import shutil
import os
from uuid import uuid4
from celery import chain
from tasks.catalog_tasks_v2 import process_catalog_file_v2, sync_catalog_dictionaries_v2

router = APIRouter()

STORAGE_DIR = "/app/storage"

@router.post("/upload_v2")
async def upload_catalog_v2(file: UploadFile = File(...), user_id: str = Form(...)):
    if not file.filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    workflow = chain(
        process_catalog_file_v2.s(file_path, user_id, file.filename),
        sync_catalog_dictionaries_v2.s(),
    )

    task_result = workflow.apply_async()

    return {
        "message": "Файл принят и поставлен в очередь на обработку (v2)",
        "task_id": task_result.id,
        "filename": file.filename
    }
