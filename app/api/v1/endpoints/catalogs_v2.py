from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import shutil
import os
from uuid import uuid4
from celery import chain
from celery.result import AsyncResult
from core.celery_app import celery_app
from tasks.catalog_tasks_v2 import generate_catalog_diff_task, process_catalog_file_v2, sync_catalog_dictionaries, sync_catalog_dictionaries_for_update

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
        sync_catalog_dictionaries.s("v2"),
    )

    task_result = workflow.apply_async()

    return {
        "message": "Файл принят и поставлен в очередь на обработку (v2)",
        "task_id": task_result.id,
        "filename": file.filename
    }




@router.post("/recalculate_diff")
async def recalculate_diff(file: UploadFile = File(...), label_id: int = Form(...)):
    if not file.filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    workflow = chain(
       
        process_catalog_file_v2.s(file_path, "system", file.filename), 
        sync_catalog_dictionaries_for_update.s("v2"),
        generate_catalog_diff_task.s(label_id=label_id)
    )

    task_result = workflow.apply_async()

    return {
        "message": "Файл принят и поставлен в очередь на перерасчёт diff",
        "task_id": task_result.id,
        "filename": file.filename
    }


@router.get("/diff_result/{task_id}")
async def get_diff_result(task_id: str):
    """Опрос результата цепочки recalculate_diff по task_id последней задачи (generate_catalog_diff_task)."""
    task_result = AsyncResult(task_id, app=celery_app)

    if not task_result.ready():
        return {"status": task_result.state, "ready": False}

    if task_result.failed():
        return {"status": "FAILURE", "ready": True, "error": str(task_result.result)}

    return {"status": "SUCCESS", "ready": True, "result": task_result.result}
